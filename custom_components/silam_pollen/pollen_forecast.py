"""
pollen_forecast.py

Сенсор прогноза уровня пыльцы для интеграции SILAM Pollen.
Использует координатор для обновления данных. Динамически формирует прогноз на основе
кэшированных агрегированных данных, полученных из merged_data.
Преобразует температуру из Кельвина в Цельсий.
"""

import logging
from datetime import datetime, timezone
from homeassistant.components.weather import WeatherEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
try:
    from homeassistant.components.weather.const import SUPPORT_FORECAST_HOURLY, SUPPORT_FORECAST_TWICE_DAILY
except ImportError:
    SUPPORT_FORECAST_HOURLY = 2
    SUPPORT_FORECAST_TWICE_DAILY = 4
from .const import DOMAIN, RESPONSIBLE_MAPPING

_LOGGER = logging.getLogger(__name__)


class PollenForecastSensor(CoordinatorEntity, WeatherEntity):
    """Сенсор прогноза уровня пыльцы для интеграции SILAM Pollen."""

    # Поддерживаются только почасовой и прогноз дважды в день
    _attr_supported_features = SUPPORT_FORECAST_HOURLY | SUPPORT_FORECAST_TWICE_DAILY
    _attr_native_temperature_unit = "°C"

    def __init__(self, coordinator, entry_id: str, base_device_name: str):
        """
        Инициализация сенсора прогноза уровня пыльцы.

        :param coordinator: Экземпляр координатора, который будет обновлять данные.
        :param entry_id: Уникальный идентификатор записи.
        :param base_device_name: Имя устройства (записи), используется для формирования имени сенсора.
        """
        CoordinatorEntity.__init__(self, coordinator)
        WeatherEntity.__init__(self)
        self._entry_id = entry_id
        self._base_device_name = base_device_name
        # Кэшированный почасовой прогноз и прогноз дважды в день,
        # которые уже агрегированы и сохранены в merged_data
        self._forecast_hourly = []
        self._forecast_twice_daily = []
        self._extra_attributes = {}
        self._attr_translation_key = "index_polen_weather"
        self._attr_has_entity_name = True
        from homeassistant.helpers.device_registry import DeviceInfo
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Возвращает дополнительные атрибуты сенсора."""
        return self._extra_attributes

    def _update_listener(self) -> None:
        """Синхронная обёртка для запуска обновления прогноза.
        
        Эта функция вызывается координатором и должна возвращать None.
        """
        self.hass.async_create_task(self._handle_coordinator_update())
        # Явно возвращаем None
        return None

    async def async_added_to_hass(self) -> None:
        """Вызывается после добавления сенсора в HA.
        
        Регистрируем слушателя обновлений через обёртку, чтобы callback возвращал None.
        Затем запускаем обновление прогноза.
        """
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._update_listener))
        await self._handle_coordinator_update()

    @property
    def unique_id(self) -> str:
        """Возвращает уникальный идентификатор для этой сущности."""
        return f"{self._entry_id}_pollen_forecast"

    @property
    def state(self) -> str | None:
        """
        Возвращает текущее состояние – значение 'condition'
        из первого элемента почасового прогноза.
        """
        if self._forecast_hourly:
            return self._forecast_hourly[0].get("condition")
        return None

    async def _handle_coordinator_update(self) -> None:
        """
        Обновляет данные сенсора, используя кэшированные данные из merged_data.

        Из объединённого словаря:
          - В разделе "hourly_forecast" берутся данные почасового прогноза.
          - В разделе "twice_daily_forecast" берутся данные прогноза дважды в день.
          - Дополнительно, для атрибутов берется раздел "now".
        """
        _LOGGER.debug("PollenForecastSensor: вызов _handle_coordinator_update")
        merged = self.coordinator.merged_data
        if not merged:
            _LOGGER.error("Объединённые данные отсутствуют для формирования прогнозов")
            return

        # Логируем содержимое для отладки
        _LOGGER.debug("Содержимое merged_data: now=%s, hourly_forecast=%s, twice_daily_forecast=%s",
                      merged.get("now"), merged.get("hourly_forecast"), merged.get("twice_daily_forecast"))

        # Обновляем почасовой прогноз
        self._forecast_hourly = merged.get("hourly_forecast", [])
        # Обновляем прогноз дважды в день
        self._forecast_twice_daily = merged.get("twice_daily_forecast", [])

        # Обновляем дополнительные атрибуты из раздела "now", если он присутствует
        now_entry = merged.get("now", {})
        if now_entry:
            polisrc_val = now_entry["data"].get("POLISRC", {}).get("value")
            try:
                re_value = int(float(polisrc_val)) if polisrc_val is not None else None
            except (ValueError, TypeError):
                re_value = None
            self._extra_attributes["responsible_elevated"] = RESPONSIBLE_MAPPING.get(re_value, "unknown")
            # Дополнительно можно добавить и другие атрибуты из now_entry

        self.async_write_ha_state()

    async def async_forecast_hourly(self) -> list[dict] | None:
        """Возвращает почасовой прогноз."""
        return self._forecast_hourly

    async def async_forecast_twice_daily(self) -> list[dict] | None:
        """Возвращает прогноз два раза в день."""
        return self._forecast_twice_daily
