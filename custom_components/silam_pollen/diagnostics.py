"""
diagnostics.py — диагностические сенсоры SILAM Pollen
"""

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType

from .const import DOMAIN
from .coordinator import SilamCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True, slots=True)
class SilamDiagnosticsSensorEntityDescription(SensorEntityDescription):
    """Описание диагностического сенсора SILAM."""


# -------------------------------------------------------------------------
# Описание диагностических сенсоров
# -------------------------------------------------------------------------
FETCH_DURATION_DESC = SilamDiagnosticsSensorEntityDescription(
    key="fetch_duration",
    translation_key="fetch_duration",
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="s",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

FORECAST_HORIZON_DESC = SilamDiagnosticsSensorEntityDescription(
    key="forecast_horizon",
    translation_key="forecast_horizon",
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="h",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

# -------------------------------------------------------------------------
# SilamPollenFetchDurationSensor
# Показывает длительность последнего обновления (сек)
# -------------------------------------------------------------------------
class SilamPollenFetchDurationSensor(SensorEntity):
    entity_description: SilamDiagnosticsSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SilamCoordinator,
        entry_id: str,
        base_device_name: str,
        description: SilamDiagnosticsSensorEntityDescription = FETCH_DURATION_DESC,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._base_device_name = base_device_name
        self.entity_description = description

        # неизменяемый unique_id
        self._attr_unique_id = f"{entry_id}_{description.key}"

        # привязываем к тому же Device, что и остальные сенсоры интеграции
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=self._base_device_name,
            entry_type=DeviceEntryType.SERVICE,
        )

        # автоматическое обновление состояния при каждом refresh координатора
        self.async_on_remove(
            coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def suggested_object_id(self) -> str:
        """Стабильный slug для entity ID"""
        return self.entity_description.key

    @property
    def native_value(self) -> float | None:
        """Последняя длительность fetch (сек)."""
        return self.coordinator.merged_data.get("last_fetch_duration")

    @property
    def extra_state_attributes(self) -> dict:
        """Диагностические атрибуты последнего фетча."""
        md = self.coordinator.merged_data
        return {
            "request_type": md.get("request_type"),
            "runs_catalog_url": md.get("runs_catalog_url"),
            "latest_run_id": md.get("latest_run_id"),
            "latest_run_start": md.get("latest_run_start"),
            "latest_run_end": md.get("latest_run_end"),
            # полезно для отладки догрузки хвоста
            "tail_fetch_attempted": md.get("tail_fetch_attempted"),
            "tail_fetch_success": md.get("tail_fetch_success"),
        }

# -------------------------------------------------------------------------
# SilamPollenForecastHorizonSensor
# Показывает горизонт прогноза (часов)
# -------------------------------------------------------------------------
class SilamPollenForecastHorizonSensor(SensorEntity):
    entity_description: SilamDiagnosticsSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SilamCoordinator,
        entry_id: str,
        base_device_name: str,
        description: SilamDiagnosticsSensorEntityDescription = FORECAST_HORIZON_DESC,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._base_device_name = base_device_name
        self.entity_description = description

        # неизменяемый unique_id
        self._attr_unique_id = f"{entry_id}_{description.key}"

        # привязываем к тому же Device, что и остальные сенсоры интеграции
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=self._base_device_name,
            entry_type=DeviceEntryType.SERVICE,
        )

        # автоматическое обновление состояния при каждом refresh координатора
        self.async_on_remove(
            coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def suggested_object_id(self) -> str:
        """Стабильный slug для entity ID"""
        return self.entity_description.key

    @property
    def native_value(self) -> float | None:
        """Горизонт прогноза в часах."""
        return self.coordinator.merged_data.get("forecast_horizon")
    @property
    def extra_state_attributes(self) -> dict:
        """Дополнительные атрибуты: длительность прогноза из настроек."""
        return {
            "forecast_duration": getattr(self.coordinator, "_forecast_duration", None)
        }