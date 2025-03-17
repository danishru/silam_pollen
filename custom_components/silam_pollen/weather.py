"""
weather.py для интеграции SILAM Pollen.

Настраивает погодные сущности для интеграции.
"""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .pollen_forecast import PollenForecastSensor
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    base_device_name = entry.title
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Координатор для погоды не найден! Проверьте сохранение координатора в __init__.py.")
        return

    async_add_entities([
        PollenForecastSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            base_device_name=base_device_name
        )
    ])
