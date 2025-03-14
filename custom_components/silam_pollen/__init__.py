from .const import DOMAIN
from .config_flow import OptionsFlowHandler as SilamPollenOptionsFlow
from .coordinator import SilamCoordinator
from .migration import async_migrate_entry
from homeassistant.helpers import entity_registry as er
from homeassistant.components.persistent_notification import async_create as persistent_notification_async_create

async def async_setup_entry(hass, entry):
    """Настраивает интеграцию через config entry."""
    # Если поле base_url отсутствует, выполняем миграцию
    if "base_url" not in entry.data:
        await async_migrate_entry(hass, entry)

    base_device_name = entry.title
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    # Извлекаем высоту из записи; если её нет, используем значение из hass.config.elevation
    desired_altitude = entry.data.get("altitude", hass.config.elevation)
    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval = entry.options.get("update_interval", entry.data.get("update_interval", 60))
    # Получаем base_url из записи; новые записи должны содержать это поле
    base_url = entry.data["base_url"]

    # Создаем экземпляр SilamCoordinator и выполняем первоначальное обновление
    coordinator = SilamCoordinator(
        hass,
        base_device_name,
        var_list,
        manual_coordinates,
        manual_latitude,
        manual_longitude,
        desired_altitude,
        update_interval,
        base_url  # Передаём параметр base_url, полученный из записи
    )
    await coordinator.async_config_entry_first_refresh()

    # Сохраняем координатор для дальнейшего использования в платформах (sensor, weather)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Пересылаем настройку на платформы sensor и weather
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "weather"])

    # Регистрируем слушатель обновления опций, чтобы при изменении опций запись перезагружалась
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def async_unload_entry(hass, entry):
    """При выгрузке перенаправляем выгрузку платформ sensor и weather, а также удаляем координатор."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "weather")
    hass.data.get(DOMAIN, {}).pop(entry.entry_id)
    return True

async def update_listener(hass, entry):
    """Обновляет запись при изменении опций, удаляя неактуальные сущности."""
    registry = er.async_get(hass)
    # Собираем ожидаемые уникальные идентификаторы для платформ sensor и weather
    expected_ids = set()
    expected_ids.add(f"{entry.entry_id}_index")
    var_list = entry.options.get("var", entry.data.get("var", []))
    for pollen in var_list:
        expected_ids.add(f"{entry.entry_id}_main_{pollen}")
    expected_ids.add(f"{entry.entry_id}_test_pollen_forecast")

    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain in ["sensor", "weather"]:
            if entity.unique_id not in expected_ids:
                registry.async_remove(entity.entity_id)
                persistent_notification_async_create(
                    hass,
                    f"Удалена сущность {entity.entity_id}, т.к. её тип пыльцы больше не выбран.",
                    title="SILAM Pollen"
                )
    await hass.config_entries.async_reload(entry.entry_id)

async def async_get_options_flow(config_entry):
    # Теперь возвращаем экземпляр OptionsFlowHandler без передачи config_entry
    return SilamPollenOptionsFlow()
