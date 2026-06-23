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

SERVICE_STATUS_OPTIONS = [
    "ok",
    "service_unavailable",
    "dataset_unavailable",
    "data_unavailable",
    "unknown",
]

SERVICE_STATUS_DESC = SilamDiagnosticsSensorEntityDescription(
    key="service_status",
    translation_key="service_status",
    device_class=SensorDeviceClass.ENUM,
    entity_category=EntityCategory.DIAGNOSTIC,
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
        md = (self.coordinator.merged_data or {}).get("diag", {})

        req = md.get("request", {})
        runs = md.get("runs_catalog", {})
        ds = md.get("dataset", {})
        cache = md.get("cache", {})

        return {
            "request_type": req.get("type"),
            "runs_catalog_url": runs.get("url"),
            "latest_run_id": runs.get("latest_run_id"),
            "latest_run_start": runs.get("latest_run_start"),
            "latest_run_end": runs.get("latest_run_end"),
            # полезно для отладки догрузки хвоста
            "tail_fetch_attempted": req.get("tail_fetch_attempted"),
            "tail_fetch_network": req.get("tail_fetch_network"),
            "tail_fetch_success": req.get("tail_fetch_success"),
            "dataset_selection": ds.get("selection"),
            "effective_base_url": ds.get("effective_base_url"),
            "preferred_base_url": ds.get("preferred_base_url"),
            # постоянный кэш raw_merged
            "cache_source": req.get("cache_source"),
            "offline_fallback": req.get("offline_fallback"),
            "cache_store_enabled": cache.get("enabled"),
            "cache_loaded": cache.get("loaded"),
            "cache_compatible": cache.get("compatible"),
            "cache_schema_version": cache.get("schema_version"),
            "cache_saved_at": cache.get("saved_at"),
            "cache_entry_title": cache.get("entry_title"),
            "cache_active_run_id": cache.get("active_run_id"),
            "cache_effective_base_url": cache.get("effective_base_url"),
            "cache_preferred_base_url": cache.get("preferred_base_url"),
            "cache_points": cache.get("points"),
            "cache_current_available": cache.get("current_available"),
            "cache_current_date": cache.get("current_date"),
            "cache_current_data_points": cache.get("current_data_points"),
            "cache_restore_payload_loaded": cache.get("restore_payload_loaded"),
        }

# -------------------------------------------------------------------------
# SilamPollenServiceStatusSensor
# Показывает короткий статус службы SILAM и подробную причину
# -------------------------------------------------------------------------
class SilamPollenServiceStatusSensor(SensorEntity):
    entity_description: SilamDiagnosticsSensorEntityDescription
    _attr_has_entity_name = True
    _attr_options = SERVICE_STATUS_OPTIONS

    def __init__(
        self,
        coordinator: SilamCoordinator,
        entry_id: str,
        base_device_name: str,
        description: SilamDiagnosticsSensorEntityDescription = SERVICE_STATUS_DESC,
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
        """Стабильный slug для entity ID."""
        return self.entity_description.key

    @property
    def native_value(self) -> str:
        """Короткий статус службы SILAM."""
        service = (self.coordinator.merged_data or {}).get("diag", {}).get("service", {})
        status = service.get("status") if isinstance(service, dict) else None
        return status if status in SERVICE_STATUS_OPTIONS else "unknown"

    @property
    def extra_state_attributes(self) -> dict:
        """Подробная причина и связанные сведения для отладки."""
        md = (self.coordinator.merged_data or {}).get("diag", {})
        service = md.get("service", {})
        root = md.get("root_catalog", {})
        runs = md.get("runs_catalog", {})
        ds = md.get("dataset", {})
        if not isinstance(service, dict):
            service = {}
        if not isinstance(root, dict):
            root = {}
        if not isinstance(runs, dict):
            runs = {}
        if not isinstance(ds, dict):
            ds = {}
        return {
            "reason": service.get("reason", "unknown"),
            "root_catalog_url": root.get("url"),
            "root_catalog_status": service.get("root_catalog_status") or root.get("status"),
            "root_catalog_ok": service.get("root_catalog_ok") if "root_catalog_ok" in service else root.get("ok"),
            "root_catalog_http_status": root.get("http_status"),
            "root_catalog_error": service.get("root_catalog_error") or root.get("error") or root.get("last_error"),
            "root_dataset_paths_count": root.get("dataset_paths_count"),
            "dataset_selection": service.get("dataset_selection") or ds.get("selection"),
            "effective_dataset": service.get("effective_dataset") or root.get("effective_dataset"),
            "effective_dataset_listed": service.get("effective_dataset_listed")
                if "effective_dataset_listed" in service
                else root.get("effective_dataset_listed"),
            "effective_base_url": ds.get("effective_base_url"),
            "preferred_dataset": service.get("preferred_dataset") or root.get("preferred_dataset"),
            "preferred_dataset_listed": service.get("preferred_dataset_listed")
                if "preferred_dataset_listed" in service
                else root.get("preferred_dataset_listed"),
            "preferred_base_url": ds.get("preferred_base_url"),
            "smart_root_skipped": service.get("smart_root_skipped")
                or root.get("smart_root_skipped"),
            "runs_catalog_url": runs.get("url"),
            "latest_run_id": runs.get("latest_run_id"),
            "latest_run_start": runs.get("latest_run_start"),
            "latest_run_end": runs.get("latest_run_end"),
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