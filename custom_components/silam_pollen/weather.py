"""
weather.py – платформа, создающая weather-сенсор SILAM Pollen.
"""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .pollen_forecast import PollenForecastSensor  # description берётся по умолчанию

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Регистрирует weather-сенсор прогноза пыльцы."""
    base_device_name = entry.title
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        _LOGGER.error(
            "Координатор не найден! Убедитесь, что он сохранён в hass.data в __init__.py"
        )
        return

    async_add_entities(
        [
            PollenForecastSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                base_device_name=base_device_name,
            )
        ],
        update_before_add=True,  # карточка сразу покажет актуальное состояние
    )
