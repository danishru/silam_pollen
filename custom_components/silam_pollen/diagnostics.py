"""
diagnostics.py

Диагностические сенсоры для интеграции SILAM Pollen.
"""

import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from .const import DOMAIN
from .coordinator import SilamCoordinator

_LOGGER = logging.getLogger(__name__)

class SilamPollenFetchDurationSensor(SensorEntity):
    """Диагностический сенсор: длительность последнего fetch (в секундах)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "fetch_duration"
    _attr_native_unit_of_measurement = "s"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SilamCoordinator, entry_id: str, base_device_name: str):
        """Инициализация диагностического сенсора."""
        super().__init__()
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._base_device_name = base_device_name

        # Привязываем сенсор к тому же устройству, что и основная интеграция
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_device_name,
            entry_type=DeviceEntryType.SERVICE,
        )

        # Подписываемся на обновления координатора, чтобы автоматически обновлять состояние
        self.async_on_remove(
            coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_fetch_duration"

    @property
    def native_value(self) -> float | None:
        """Время последнего fetch в секундах."""
        return self.coordinator.merged_data.get("last_fetch_duration")