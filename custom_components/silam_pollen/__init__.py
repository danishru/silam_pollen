from .const import DOMAIN
from .config_flow import OptionsFlowHandler as SilamPollenOptionsFlow
from homeassistant.helpers import entity_registry as er
# Импорт функции для создания уведомлений напрямую
from homeassistant.components.persistent_notification import async_create as persistent_notification_async_create

async def async_setup_entry(hass, entry):
    """Настраивает интеграцию через config entry."""
    # Перенаправляем настройку сенсоров
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    async def async_force_update(call):
        entity_id = call.data.get("entity_id")
        if entity_id:
            hass.async_create_task(
                hass.services.async_call("homeassistant", "update_entity", {"entity_id": entity_id})
            )
        else:
            hass.async_create_task(
                hass.services.async_call("homeassistant", "update_entity", {"entity_id": "sensor.silam_pollen_alder"})
            )

    # Регистрируем сервис force_update и регистрируем его на отмену при выгрузке
    hass.services.async_register(DOMAIN, "force_update", async_force_update)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "force_update"))
    
    # Регистрируем слушатель обновления опций, чтобы при изменении опций запись перезагружалась
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_unload_entry(hass, entry):
    # При выгрузке перенаправляем выгрузку сенсоров
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True

async def update_listener(hass, entry):
    """Обновляет запись при изменении опций, удаляя неактуальные сенсоры."""
    registry = er.async_get(hass)
    # Вычисляем ожидаемые уникальные идентификаторы сенсоров
    expected_ids = set()
    # Уникальный id для сводного сенсора "index"
    expected_ids.add(f"{entry.entry_id}_index")
    # Уникальные id для сенсоров каждого выбранного типа пыльцы
    var_list = entry.options.get("var", entry.data.get("var", []))
    for pollen in var_list:
        expected_ids.add(f"{entry.entry_id}_main_{pollen}")

    # Проходим по всем сенсорам, связанным с данной записью
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain == "sensor":
            if entity.unique_id not in expected_ids:
                registry.async_remove(entity.entity_id)
                persistent_notification_async_create(
                    hass,
                    f"Удалён сенсор {entity.entity_id}, т.к. его тип пыльцы больше не выбран.",
                    title="SILAM Pollen"
                )
    # Перезагружаем запись для пересоздания актуальных сенсоров
    await hass.config_entries.async_reload(entry.entry_id)

async def async_get_options_flow(config_entry):
    return SilamPollenOptionsFlow(config_entry)
