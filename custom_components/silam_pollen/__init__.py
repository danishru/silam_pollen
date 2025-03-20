import logging
import voluptuous as vol
from homeassistant.helpers import entity_registry as er
from homeassistant.components.persistent_notification import async_create as persistent_notification_async_create
from homeassistant.helpers import config_validation as cv
from homeassistant.core import SupportsResponse

from .const import DOMAIN
from .config_flow import OptionsFlowHandler as SilamPollenOptionsFlow
from .coordinator import SilamCoordinator
from .migration import async_migrate_entry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Настраивает интеграцию SILAM Pollen через config entry."""
    # Запускаем миграцию, если версия равна 1 и minor_version меньше 2.
    if entry.version == 1 and entry.minor_version < 2:
        await async_migrate_entry(hass, entry)

    base_device_name = entry.title
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    # Если высота не указана, используем значение из hass.config.elevation.
    desired_altitude = entry.data.get("altitude", hass.config.elevation)
    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval = entry.options.get("update_interval", entry.data.get("update_interval", 60))
    forecast_enabled = entry.options.get("forecast", entry.data.get("forecast", False))
    base_url = entry.data["base_url"]

    # Создаем координатор для обновления данных.
    coordinator = SilamCoordinator(
        hass,
        base_device_name,
        var_list,
        manual_coordinates,
        manual_latitude,
        manual_longitude,
        desired_altitude,
        update_interval,
        base_url,
        forecast=forecast_enabled
    )
    await coordinator.async_config_entry_first_refresh()

    # Сохраняем координатор для дальнейшего использования в платформах (sensor, weather).
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Определяем список платформ: всегда sensor, а weather – только если включена опция forecast.
    platforms = ["sensor"]
    if forecast_enabled:
        platforms.append("weather")
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Регистрируем службу ручного обновления, которая возвращает merged_data для обновлённых записей.
    # Данные цели передаются через ключ "targets" с вложенными списками "device_id" и "entity_id".
    from homeassistant.helpers.device_registry import async_get as async_get_device_registry

    async def handle_manual_update(call):
        """Обработчик службы для ручного обновления данных для выбранных устройств/сущностей.
        
        Возвращает данные обновлённых записей в формате:
        {"updated_entries": {<device_name>: merged_data, ...}}
        """
        updated_data = {}
        targets = call.data.get("targets", {})
        device_ids = targets.get("device_id", [])
        entity_ids = targets.get("entity_id", [])

        if not device_ids and not entity_ids:
            _LOGGER.warning("Для ручного обновления не выбрана ни одна цель")
            return {"updated_entries": updated_data}

        # Получаем реестр устройств (синхронно, без await).
        device_registry = async_get_device_registry(hass)

        # Обрабатываем выбранные устройства.
        for device_id in device_ids:
            device_entry = device_registry.async_get(device_id)
            if not device_entry:
                _LOGGER.error("Устройство с id %s не найдено", device_id)
                continue
            # Для каждого идентификатора устройства, если он принадлежит нашей интеграции,
            # используем entry_id для поиска координатора и его базового имени.
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN:
                    entry_id = identifier[1]
                    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
                    if coordinator:
                        await coordinator.async_request_refresh()
                        updated_data[coordinator._base_device_name] = coordinator.merged_data
                        _LOGGER.debug("Запущено ручное обновление для записи %s", entry_id)
                    else:
                        _LOGGER.error("Координатор для записи %s не найден", entry_id)

        # Обрабатываем выбранные сущности.
        for entity_id in entity_ids:
            registry = er.async_get(hass)
            entity_entry = registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.error("Сущность с id %s не найдена", entity_id)
                continue
            # Получаем device_id из записи сущности.
            dev_id = entity_entry.device_id
            if not dev_id:
                _LOGGER.error("Сущность %s не связана с устройством", entity_id)
                continue
            device_entry = device_registry.async_get(dev_id)
            if not device_entry:
                _LOGGER.error("Устройство для сущности %s не найдено", entity_id)
                continue
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN:
                    entry_id = identifier[1]
                    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
                    if coordinator:
                        await coordinator.async_request_refresh()
                        # Если для этого устройства уже добавлено значение, не перезаписываем.
                        if coordinator._base_device_name not in updated_data:
                            updated_data[coordinator._base_device_name] = coordinator.merged_data
                        _LOGGER.debug("Запущено ручное обновление для записи %s (сущность)", entry_id)
                    else:
                        _LOGGER.error("Координатор для записи %s не найден", entry_id)

        return {"updated_entries": updated_data}

    hass.services.async_register(
        DOMAIN,
        "manual_update",
        handle_manual_update,
        schema=vol.Schema({
            vol.Required("targets"): {
                vol.Optional("device_id"): vol.All(cv.ensure_list, [str]),
                vol.Optional("entity_id"): vol.All(cv.ensure_list, [str])
            }
        }),
        supports_response=SupportsResponse.OPTIONAL
    )

    # Регистрируем слушатель обновления опций, чтобы при изменении опций запись перезагружалась.
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def async_unload_entry(hass, entry):
    """Отключает платформы интеграции и удаляет сохранённые данные координатора."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    forecast_enabled = entry.options.get("forecast", entry.data.get("forecast", False))
    if forecast_enabled:
        try:
            await hass.config_entries.async_forward_entry_unload(entry, "weather")
        except Exception as err:
            _LOGGER.warning("Weather platform unload error for entry %s: %s", entry.entry_id, err)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id)
    return True

async def update_listener(hass, entry):
    """Обновляет запись при изменении опций, удаляя устаревшие сущности."""
    registry = er.async_get(hass)
    expected_ids = set()
    # Ожидается сенсор "index".
    expected_ids.add(f"{entry.entry_id}_index")
    # Ожидаются сенсоры "main" для выбранных аллергенов.
    var_list = entry.options.get("var", entry.data.get("var", []))
    for pollen in var_list:
        expected_ids.add(f"{entry.entry_id}_main_{pollen}")
    # Если включен режим forecast, ожидается погодный сенсор с уникальным идентификатором _pollen_forecast.
    forecast_enabled = entry.options.get("forecast", entry.data.get("forecast", False))
    if forecast_enabled:
        expected_ids.add(f"{entry.entry_id}_pollen_forecast")

    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain in ["sensor", "weather"]:
            if entity.unique_id not in expected_ids:
                registry.async_remove(entity.entity_id)
                persistent_notification_async_create(
                    hass,
                    f"Сущность {entity.entity_id} удалена, так как выбранный тип пыльцы более не используется.",
                    title="SILAM Pollen"
                )
    await hass.config_entries.async_reload(entry.entry_id)

async def async_get_options_flow(config_entry):
    """Возвращает обработчик Options Flow для данной записи."""
    return SilamPollenOptionsFlow()
