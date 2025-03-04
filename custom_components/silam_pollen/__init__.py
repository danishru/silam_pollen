DOMAIN = "silam_pollen"

async def async_setup_entry(hass, entry):
    """Настраивает интеграцию через config entry."""
    # Используйте новый метод для форвардинга платформ (в данном случае только "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    async def async_force_update(call):
        """Пример пользовательской службы для обновления сенсоров."""
        entity_id = call.data.get("entity_id")
        if entity_id:
            hass.async_create_task(
                hass.services.async_call("homeassistant", "update_entity", {"entity_id": entity_id})
            )
        else:
            hass.async_create_task(
                hass.services.async_call("homeassistant", "update_entity", {"entity_id": "sensor.silam_pollen_alder"})
            )

    hass.services.async_register(DOMAIN, "force_update", async_force_update)
    return True

async def async_unload_entry(hass, entry):
    """Выгружает интеграцию."""
    await hass.config_entries.async_forward_entry_unloads(entry, ["sensor"])
    return True
