"""
test_pollen.py

Тестовый сенсор прогноза уровня пыльцы для интеграции SILAM Pollen.
Использует координатор для обновления данных. Сейчас генерирует статичный прогноз,
но в будущем данные можно будет получать из coordinator.data.
"""

import logging
from datetime import datetime, timedelta
from homeassistant.components.weather import WeatherEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
try:
    from homeassistant.components.weather.const import SUPPORT_FORECAST_DAILY, SUPPORT_FORECAST_HOURLY
except ImportError:
    SUPPORT_FORECAST_DAILY = 1
    SUPPORT_FORECAST_HOURLY = 2
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class TestPollenForecastSensor(CoordinatorEntity, WeatherEntity):
    """Сенсор прогноза уровня пыльцы, использующий координатор для обновления данных."""

    _attr_icon = "mdi:weather-hazy"
    _attr_supported_features = SUPPORT_FORECAST_DAILY | SUPPORT_FORECAST_HOURLY

    def __init__(self, coordinator, entry_id: str, base_device_name: str):
        """
        Инициализация тестового сенсора.
        
        :param coordinator: Экземпляр координатора, который будет обновлять данные.
        :param entry_id: Уникальный идентификатор записи.
        :param base_device_name: Имя устройства (записи), используется для формирования имени сенсора.
        """
        CoordinatorEntity.__init__(self, coordinator)
        WeatherEntity.__init__(self)
        self._entry_id = entry_id
        self._base_device_name = base_device_name
        self._forecast_daily = []
        self._forecast_hourly = []
        self._attr_name = f"{self._base_device_name} Forecast"
        self._attr_translation_key = "test_pollen_forecast"
        # Привязываем сенсор к устройству записи (только идентификаторы)
        from homeassistant.helpers.device_registry import DeviceInfo
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Вызывается после добавления сенсора в HA. Немедленно обновляем прогноз."""
        await super().async_added_to_hass()
        await self._handle_coordinator_update()

    @property
    def unique_id(self) -> str:
        """Возвращает уникальный идентификатор для этой сущности."""
        return f"{self._entry_id}_test_pollen_forecast"

    @property
    def state(self) -> str | None:
        """
        Возвращает текущее состояние – например, значение 'condition'
        из первого элемента ежедневного прогноза.
        """
        if self._forecast_daily:
            return self._forecast_daily[0].get("condition")
        return None

    async def _handle_coordinator_update(self) -> None:
        """
        Обработчик обновления данных от координатора.

        Здесь для тестирования генерируется статичный прогноз.
        """
        _LOGGER.debug("TestPollenForecastSensor: вызов _handle_coordinator_update")
        now = datetime.utcnow()

        # 7-дневный прогноз: для каждого дня от 1 до 7
        self._forecast_daily = []
        for i in range(1, 8):
            forecast_date = now + timedelta(days=i)
            if i % 3 == 1:
                condition = "lightning-rainy"
                pollen_index = 1
                temp = 0 + i
                templow = 15 + i
                desc = "Very low pollen count"
            elif i % 3 == 2:
                condition = "rainy"
                pollen_index = 3
                temp = 222 + i
                templow = 16 + i
                desc = "Moderate pollen count"
            else:
                condition = "sunny"
                pollen_index = 5
                temp = 4524 + i
                templow = 18 + i
                desc = "High pollen count"
            self._forecast_daily.append({
                "datetime": forecast_date.isoformat() + "Z",
                "condition": condition,
                "native_temperature": temp,
                "native_templow": templow,
                "native_precipitation": pollen_index,
                "native_precipitation_unit": "pollen",
                "pollen_index": pollen_index,
                "pollen_description": desc,
            })

        # Почасовой прогноз: 6 прогнозных периодов для следующих 6 часов
        self._forecast_hourly = []
        for i in range(1, 7):
            forecast_time = now + timedelta(hours=i)
            if i % 3 == 1:
                condition = "moderate"
                pollen_index = 1
                temp = 2012 + i
                templow = 15 + i
                desc = "Very low pollen count"
            elif i % 3 == 2:
                condition = "sunny"
                pollen_index = 3
                temp = 222 + i
                templow = 16 + i
                desc = "Moderate pollen count"
            else:
                condition = "exceptional"
                pollen_index = 5
                temp = 24 + i
                templow = 18 + i
                desc = "High pollen count"
            self._forecast_hourly.append({
                "datetime": forecast_time.isoformat() + "Z",
                "condition": condition,
                "native_temperature": temp,
                "native_templow": templow,
                "native_precipitation": pollen_index,
                "native_precipitation_unit": "pollen",
                "pollen_index": pollen_index,
                "pollen_description": desc,
            })

        self.async_write_ha_state()

    async def async_forecast_daily(self) -> list[dict] | None:
        """Возвращает 7-дневный прогноз."""
        return self._forecast_daily

    async def async_forecast_hourly(self) -> list[dict] | None:
        """Возвращает почасовой прогноз."""
        return self._forecast_hourly
