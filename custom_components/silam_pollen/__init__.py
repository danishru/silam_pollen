DOMAIN = "silam_pollen"

async def async_setup_entry(hass, entry):
    """Настраивает интеграцию из UI (config flow)."""
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    return True

async def async_unload_entry(hass, entry):
    """Разгружает интеграцию при удалении."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True
