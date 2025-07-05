"""
pollen_forecast.py

Сенсор прогноза уровня пыльцы для интеграции **SILAM Pollen**.

• Использует координатор, читающий объединённые данные (`merged_data`)  
• Формирует почасовой и дважды-в-день прогнозы  
• Возвращает стабильный entity_id вида `weather.silam_pollen_<zone>_forecast`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from homeassistant.components.weather import WeatherEntity
from homeassistant.helpers.entity import EntityDescription, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# В некоторых старых релизах HA константы могут отсутствовать
try:
    from homeassistant.components.weather.const import (
        SUPPORT_FORECAST_HOURLY,
        SUPPORT_FORECAST_TWICE_DAILY,
    )
except ImportError:
    SUPPORT_FORECAST_HOURLY = 2
    SUPPORT_FORECAST_TWICE_DAILY = 4

from .const import DOMAIN, RESPONSIBLE_MAPPING, INDEX_MAPPING 

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Декларативное описание weather-сенсора
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True, kw_only=True)
class SilamWeatherEntityDescription(EntityDescription):
    """Минимальное (расширяемое) описание weather-сенсора SILAM."""


FORECAST_DESC = SilamWeatherEntityDescription(
    key="forecast",
    translation_key="forecast",
)

# ---------------------------------------------------------------------------
#  Класс сущности
# ---------------------------------------------------------------------------


class PollenForecastSensor(CoordinatorEntity, WeatherEntity):
    """Weather-сенсор прогноза уровня пыльцы."""

    entity_description: SilamWeatherEntityDescription
    _attr_has_entity_name = True
    _attr_supported_features = SUPPORT_FORECAST_HOURLY | SUPPORT_FORECAST_TWICE_DAILY
    _attr_native_temperature_unit = "°C"

    def __init__(
        self,
        coordinator,
        entry_id: str,
        base_device_name: str,
        description: SilamWeatherEntityDescription = FORECAST_DESC,
    ) -> None:
        """
        Инициализация сенсора прогноза уровня пыльцы.

        :param coordinator: Экземпляр CoordinatorEntity с merged_data  
        :param entry_id: Уникальный ID ConfigEntry  
        :param base_device_name: Читаемое имя устройства для UI  
        """
        CoordinatorEntity.__init__(self, coordinator)
        WeatherEntity.__init__(self)

        self._entry_id = entry_id
        self._base_device_name = base_device_name
        self.entity_description = description

        # Стабильный unique_id («entry + slug») — не зависит от локали.
        self._attr_unique_id = f"{entry_id}_pollen_forecast"
        self._attr_translation_key = description.translation_key

        # Привязываемся к тому же Device, что и остальные сенсоры интеграции
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=base_device_name,
        )

        # Кэш прогнозов и дополнительных атрибутов
        self._forecast_hourly: list[dict] = []
        self._forecast_twice_daily: list[dict] = []
        self._extra_attributes: dict = {}
        self._current_condition: str | None = None

    # ---------------------------------------------------------------------
    #  Метаданные Home Assistant
    # ---------------------------------------------------------------------

    @property
    def suggested_object_id(self) -> str:
        """Постоянный slug `forecast` → entity_id фиксируется как `…_forecast`."""
        return self.entity_description.key

    # ---------------------------------------------------------------------
    #  Значения и атрибуты сенсора
    # ---------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict:
        """Дополнительные атрибуты (ответственный аллерген и т. д.)."""
        return self._extra_attributes

    @property
    def state(self) -> str | None:
        """Текущее состояние (very_low … very_high) из блока «now»."""
        return self._current_condition

    # ---------------------------------------------------------------------
    #  Обработка обновлений координатора
    # ---------------------------------------------------------------------

    def _update_listener(self) -> None:  # noqa: D401 (simple name)
        """Запускает асинхронное обновление при каждом refresh координатора."""
        self.hass.async_create_task(self._handle_coordinator_update())
        return None  # явно — Coordinator ожидает None

    async def async_added_to_hass(self) -> None:
        """Настраивает подписку на координатор и делает первое обновление."""
        await super().async_added_to_hass()
        if hasattr(self, "_unsub_coordinator_listener") and self._unsub_coordinator_listener:
            self._unsub_coordinator_listener()
            self._unsub_coordinator_listener = None
        self.async_on_remove(
            self.coordinator.async_add_listener(self._update_listener)
        )
        await self._handle_coordinator_update()

    async def _handle_coordinator_update(self) -> None:
        """
        Извлекает прогнозы и атрибуты из `merged_data` координатора.

        Ожидает структуру:
        {
            "hourly_forecast": [...],
            "twice_daily_forecast": [...],
            "now": {
                "data": {
                    "POLISRC": {"value": "5"}
                }
            }
        }
        """
        merged = self.coordinator.merged_data
        if not merged:
            _LOGGER.warning("merged_data пуст — прогноз не обновлён")
            return

        # Прогнозы
        self._extra_attributes = {}
        self._forecast_hourly = merged.get("hourly_forecast", [])
        self._forecast_twice_daily = merged.get("twice_daily_forecast", [])

        # --- ближайшее (next) состояние из 1-го интервала hourly -----------
        if self._forecast_hourly:
            self._extra_attributes["next_condition"] = (
                self._forecast_hourly[0].get("condition")
            )

        # Текущий индекс + «ответственный аллерген» из блока now
        now_entry = merged.get("now", {})
        if now_entry:
            # --- 1. дата «сейчас» (как в sensor.index)
            self._extra_attributes["date"] = now_entry.get("date")  # <--- добавлено
            # --- 2. Индекс POLI → condition ---------------------------------
            poli_val = now_entry["data"].get("POLI", {}).get("value")
            try:
                idx_val = int(float(poli_val)) if poli_val is not None else None
            except (ValueError, TypeError):
                idx_val = None
            self._current_condition = INDEX_MAPPING.get(idx_val, "unknown")

            # --- 3. Ответственный аллерген POLISRC ---------------------------
            polisrc_val = now_entry["data"].get("POLISRC", {}).get("value")
            try:
                re_value = int(float(polisrc_val)) if polisrc_val is not None else None
            except (ValueError, TypeError):
                re_value = None
            self._extra_attributes["responsible_elevated"] = RESPONSIBLE_MAPPING.get(
                re_value, "unknown"
            )

        self.async_write_ha_state()

    # ---------------------------------------------------------------------
    #  API WeatherEntity — карточки HA используют эти методы
    # ---------------------------------------------------------------------

    async def async_forecast_hourly(self) -> list[dict] | None:
        """Возвращает почасовой прогноз (до 48 ч)."""
        return self._forecast_hourly

    async def async_forecast_twice_daily(self) -> list[dict] | None:
        """Возвращает прогноз «день/ночь» на несколько суток."""
        return self._forecast_twice_daily
