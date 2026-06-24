"""Инициализация интеграции SILAM Pollen."""

from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components.persistent_notification import (
    async_create as persistent_notification_async_create,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CACHE_STORES,
    DOMAIN,
    RUNS_CATALOG_MANAGER,
    RUNS_CATALOG_TTL_SECONDS,
    SILAM_CATALOG_MANAGER,
)
from .silam_catalog import SilamCatalogManager
from .config_flow import OptionsFlowHandler as SilamPollenOptionsFlow
from .coordinator import SilamCoordinator
from .cache_store import SilamPollenCacheStore, async_remove_entry_cache
from .migration import async_migrate_entry  # ядро вызовет при необходимости
from .repairs import (
    async_delete_legacy_index_sensor_deprecated_issue,
    async_delete_manual_dataset_unavailable_issue,
    async_update_legacy_index_sensor_deprecated_issue,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# -----------------------------------------------------------------------------
#  Глобальная инициализация: выполняется один раз при старте Home Assistant
# -----------------------------------------------------------------------------
async def async_setup(hass, _config):
    """Регистрация глобальных сервисов (выполняется один раз за ядро)."""
    # Безопасно импортируем здесь, не на верхнем уровне
    try:
        from .config_flow import SilamPollenConfigFlow
        _LOGGER.debug(
            "ConfigFlow VERSION is %s.%s",
            getattr(SilamPollenConfigFlow, "VERSION", None),
            getattr(SilamPollenConfigFlow, "MINOR_VERSION", 0),
        )
    except Exception as e:
        _LOGGER.debug("ConfigFlow version check skipped: %s", e)

    if not hass.data.get("absolute_forecast_card_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/local/absolute-forecast-card.js",
                hass.config.path("custom_components", DOMAIN, "absolute-forecast-card.js"),
                False,
            )
        ])
        hass.data["absolute_forecast_card_registered"] = True

    # Импорт внутри функции, чтобы не тащить зависимость при unit-тестах без HA
    from homeassistant.helpers.device_registry import async_get as async_get_device_registry

    update_devices_schema = vol.Schema(
        {
            vol.Required("device_id"): vol.All(cv.ensure_list, [str]),
        }
    )

    manual_update_schema = vol.Schema(
        {
            vol.Optional("device_id"): vol.All(cv.ensure_list, [str]),
            # Легаси-совместимость: старые автоматизации могли передавать
            # выбранные цели через поле `targets` из прежнего target selector.
            # В UI это поле больше не показываем, но backend принимает его,
            # чтобы не ломать существующие scripts/automations после обновления.
            vol.Optional("targets"): {
                vol.Optional("device_id"): vol.All(cv.ensure_list, [str]),
                vol.Optional("entity_id"): vol.All(cv.ensure_list, [str]),
            },
        }
    )

    def _extract_update_targets(call):
        """Получить новые device_id и легаси targets для manual_update."""
        device_ids = list(call.data.get("device_id", []))
        entity_ids: list[str] = []

        # Легаси-совместимость: поддерживаем старый формат:
        # data.targets.device_id / data.targets.entity_id.
        legacy_targets = call.data.get("targets", {})
        if legacy_targets:
            _LOGGER.debug("manual_update: legacy targets payload used")
            device_ids.extend(legacy_targets.get("device_id", []))
            entity_ids.extend(legacy_targets.get("entity_id", []))

        # Убираем повторы, сохраняя порядок. Это защищает от двойного refresh,
        # если одна и та же служба SILAM Pollen выбрана и как device, и через entity.
        return list(dict.fromkeys(device_ids)), list(dict.fromkeys(entity_ids))

    async def _handle_update_service(call, *, force_full_refresh: bool):
        """Обработать ручное обновление выбранных служб интеграции."""
        updated_data: dict[str, dict] = {}
        service_name = "full_refresh" if force_full_refresh else "manual_update"

        if force_full_refresh:
            device_ids = list(call.data.get("device_id", []))
            entity_ids: list[str] = []
        else:
            device_ids, entity_ids = _extract_update_targets(call)

        if not device_ids and not entity_ids:
            _LOGGER.warning("%s: no SILAM Pollen services provided", service_name)
            return {"updated_entries": updated_data} if call.return_response else None

        device_registry = async_get_device_registry(hass)
        registry = er.async_get(hass) if entity_ids else None
        refreshed_entries: set[str] = set()

        async def _refresh(entry_id: str) -> None:
            """Запросить обновление у нужного координатора."""
            if entry_id in refreshed_entries:
                return
            refreshed_entries.add(entry_id)

            coordinator: SilamCoordinator | None = hass.data.get(DOMAIN, {}).get(entry_id)
            if coordinator:
                if force_full_refresh:
                    try:
                        await coordinator.async_request_full_refresh()
                    except Exception as err:  # noqa: BLE001 - service action должен вернуть пользователю ошибку
                        base_name = coordinator._base_device_name  # noqa: SLF001
                        _LOGGER.error(
                            "full_refresh failed for %s: %s",
                            base_name,
                            err,
                        )
                        raise HomeAssistantError(
                            f"SILAM Pollen full refresh failed for {base_name}: {err}"
                        ) from err
                else:
                    await coordinator.async_request_refresh()
                # _base_device_name — приватный атрибут; переедет в public-property позже
                updated_data.setdefault(
                    coordinator._base_device_name, coordinator.merged_data  # noqa: SLF001
                )
            else:
                _LOGGER.error("Coordinator for entry %s not found", entry_id)

        for dev_id in device_ids:
            dev_entry = device_registry.async_get(dev_id)
            if not dev_entry:
                _LOGGER.error("Device %s not found", dev_id)
                continue
            for domain, entry_id in dev_entry.identifiers:
                if domain == DOMAIN:
                    await _refresh(entry_id)

        # Легаси-совместимость: старый manual_update мог принимать entity_id
        # через data.targets.entity_id. Новый UI больше не предлагает entity targets,
        # но старые YAML scripts/automations должны продолжить работать.
        if registry is not None:
            for ent_id in entity_ids:
                ent_entry = registry.async_get(ent_id)
                if not ent_entry or not ent_entry.device_id:
                    _LOGGER.error("Entity %s is not linked to a device", ent_id)
                    continue
                dev_entry = device_registry.async_get(ent_entry.device_id)
                if not dev_entry:
                    _LOGGER.error("Device for entity %s not found", ent_id)
                    continue
                for domain, entry_id in dev_entry.identifiers:
                    if domain == DOMAIN:
                        await _refresh(entry_id)

        # Возвращаем данные только если вызов сделан с return_response=True
        return {"updated_entries": updated_data} if call.return_response else None

    async def handle_manual_update(call):
        """Обработчик обычного ручного обновления выбранных служб."""
        return await _handle_update_service(call, force_full_refresh=False)

    async def handle_full_refresh(call):
        """Обработчик принудительного полного обновления выбранных служб."""
        return await _handle_update_service(call, force_full_refresh=True)

    if not hass.services.has_service(DOMAIN, "manual_update"):
        hass.services.async_register(
            DOMAIN,
            "manual_update",
            handle_manual_update,
            schema=manual_update_schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, "full_refresh"):
        hass.services.async_register(
            DOMAIN,
            "full_refresh",
            handle_full_refresh,
            schema=update_devices_schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

    return True

# -----------------------------------------------------------------------------
#  Настройка конкретной записи ConfigEntry
# -----------------------------------------------------------------------------
async def async_setup_entry(hass, entry):
    """Настроить интеграцию SILAM Pollen по конфигурационной записи."""
    base_device_name = entry.title
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    desired_altitude = entry.data.get("altitude", hass.config.elevation)

    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval = entry.options.get(
        "update_interval", entry.data.get("update_interval", 60)
    )
    forecast_enabled = entry.options.get(
        "forecast", entry.data.get("forecast", False)
    )
    forecast_duration = int(
        entry.options.get("forecast_duration", entry.data.get("forecast_duration", 36))
    )
    base_url = entry.data["base_url"]

    # ---------------------------------------------------------------------
    # Политика выбора датасета (SMART vs фиксированный)
    # - SMART: координатор (сейчас/в будущем) сможет пере-выбирать лучший датасет
    #   и затем (позже) догружать недостающие данные из других наборов.
    # - Фиксированный: использовать только выбранный датасет, без попыток альтернатив.
    # ---------------------------------------------------------------------
    dataset_selection = entry.options.get("version", entry.data.get("version", "smart"))

    # Кандидаты для SMART (в порядке приоритета).
    candidates: list[str] = []
    try:
        # Локальный импорт, чтобы не плодить циклы и не тянуть лишнее при unit-тестах
        from .const import dataset_base_url, iter_datasets_for_probe

        for dataset_name in iter_datasets_for_probe():
            _v = dataset_base_url(dataset_name)
            if isinstance(_v, str) and _v and _v not in candidates:
                candidates.append(_v)
    except Exception:
        # Если по какой-то причине не смогли собрать кандидатов — не падаем,
        # координатор хотя бы получит текущий base_url ниже.
        pass

    # Гарантируем, что текущий base_url есть в списке (на случай кастомных/будущих URL),
    # но НЕ первым — иначе SMART никогда не переключится на более подходящий датасет.
    if isinstance(base_url, str) and base_url and base_url not in candidates:
        candidates.append(base_url)

    # Инициализируем общий SilamCatalogManager (один на DOMAIN).
    # На этом шаге фасад содержит только RunsCatalogManager, поэтому поведение
    # координатора не меняется. Старый ключ RUNS_CATALOG_MANAGER оставляем
    # как compatibility layer для текущего coordinator.py и hot-reload.
    domain_data = hass.data.setdefault(DOMAIN, {})
    catalog_manager = domain_data.get(SILAM_CATALOG_MANAGER)
    if catalog_manager is None:
        catalog_manager = SilamCatalogManager(
            hass,
            ttl_seconds=RUNS_CATALOG_TTL_SECONDS,
            runs_manager=domain_data.get(RUNS_CATALOG_MANAGER),
        )
        domain_data[SILAM_CATALOG_MANAGER] = catalog_manager
        _LOGGER.debug("SILAM Pollen: initialized SilamCatalogManager")

    domain_data[RUNS_CATALOG_MANAGER] = catalog_manager.runs

    # Постоянный кэш для этой ConfigEntry:
    # читаем совместимый payload при setup и передаём его координатору.
    # Координатор сам решает, можно ли восстановиться после проверки run_id.
    cache_store = SilamPollenCacheStore(
        hass,
        entry,
        base_url=base_url,
        selected_allergens=var_list,
        forecast_enabled=forecast_enabled,
        forecast_duration=forecast_duration,
        dataset_selection=dataset_selection,
        latitude=manual_latitude,
        longitude=manual_longitude,
        altitude=desired_altitude,
    )
    cached_payload = await cache_store.async_initialize()
    domain_data.setdefault(CACHE_STORES, {})[entry.entry_id] = cache_store

    # Создаём координатор
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
        dataset_selection=dataset_selection,
        smart_candidates=candidates,
        forecast=forecast_enabled,
        forecast_duration=forecast_duration,
        cache_store=cache_store,
        cached_payload=cached_payload,
        config_entry_id=entry.entry_id,
    )
    await coordinator.async_config_entry_first_refresh()

    # Сохраняем координатор для последующего доступа
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Подключаем платформы
    platforms = ["sensor", "weather"]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Если у пользователя ещё создан устаревший index-сенсор, показываем
    # Repair warning. Сам сенсор пока не удаляем: пользователю нужно спокойно
    # перенастроить automations/scripts на новый weather-сенсор прогноза.
    await async_update_legacy_index_sensor_deprecated_issue(
        hass,
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )

    # Слушатель изменений опций
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass, entry):
    """Выключить платформы и убрать координатор при удалении записи."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "weather")
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)
    domain_data.get(CACHE_STORES, {}).pop(entry.entry_id, None)
    await async_delete_manual_dataset_unavailable_issue(hass, entry_id=entry.entry_id)
    await async_delete_legacy_index_sensor_deprecated_issue(hass, entry_id=entry.entry_id)
    return True



async def async_remove_entry(hass, entry) -> None:
    """Удалить файл постоянного кэша при удалении ConfigEntry пользователем."""
    await async_delete_manual_dataset_unavailable_issue(hass, entry_id=entry.entry_id)
    await async_delete_legacy_index_sensor_deprecated_issue(hass, entry_id=entry.entry_id)
    domain_data = hass.data.get(DOMAIN, {})
    cache_store = domain_data.get(CACHE_STORES, {}).pop(entry.entry_id, None)

    if cache_store is not None:
        await cache_store.async_remove()
        return

    await async_remove_entry_cache(
        hass,
        entry.entry_id,
        entry_title=getattr(entry, "title", None),
    )


async def _async_reload_entry_in_background(hass, entry_id: str) -> None:
    """Перезагрузить ConfigEntry после изменения опций без блокировки Options Flow."""
    try:
        await hass.config_entries.async_reload(entry_id)
    except Exception:  # noqa: BLE001 - фоновая задача не должна терять ошибку в тишине
        _LOGGER.exception(
            "SILAM Pollen: background reload failed for entry %s",
            entry_id,
        )


async def update_listener(hass, entry):
    """Удалить устаревшие сущности после изменения опций и перезагрузить запись."""
    registry = er.async_get(hass)

    # Опции/данные
    var_list = entry.options.get("var", entry.data.get("var", []))
    forecast_enabled = entry.options.get("forecast", entry.data.get("forecast", False))
    legacy_enabled = entry.options.get("legacy", entry.data.get("legacy", False))

    # Ожидаемые unique_id
    expected_ids: set[str] = {
        f"{entry.entry_id}_fetch_duration",
        f"{entry.entry_id}_forecast_horizon",
        f"{entry.entry_id}_service_status",
    }

    # Индекс — только если включён legacy
    if legacy_enabled:
        expected_ids.add(f"{entry.entry_id}_index")

    # Основные сенсоры по аллергенам
    expected_ids.update(f"{entry.entry_id}_main_{p}" for p in var_list)

    # Погодный сенсор прогноза — только если включён forecast
    if forecast_enabled:
        expected_ids.add(f"{entry.entry_id}_pollen_forecast")

    # Удаляем всё лишнее
    for entity in list(registry.entities.values()):
        if (
            entity.config_entry_id == entry.entry_id
            and entity.domain in {"sensor", "weather"}
            and entity.unique_id not in expected_ids
        ):
            registry.async_remove(entity.entity_id)

            # ПРИМЕЧАНИЕ: у тебя этот блок был закомментирован — оставляю так же.
            # persistent_notification_async_create(
            #     hass,
            #     (
            #         f"Сущность {entity.entity_id} удалена, "
            #         "так как выбранный тип пыльцы или опции были изменены."
            #     ),
            #     title="SILAM Pollen",
            # )

    await async_update_legacy_index_sensor_deprecated_issue(
        hass,
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )

    # Не ждём тяжёлую перезагрузку записи внутри Options Flow.
    # После изменения опций HA должен быстро закрыть окно настроек,
    # а сетевой refresh/backfill координатора выполнится уже в фоне.
    hass.async_create_task(
        _async_reload_entry_in_background(hass, entry.entry_id)
    )


async def async_get_options_flow(config_entry):
    """Вернуть обработчик Options Flow."""
    return SilamPollenOptionsFlow()
