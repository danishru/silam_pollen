"""Инициализация интеграции SILAM Pollen."""

from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components.persistent_notification import (
    async_create as persistent_notification_async_create,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .config_flow import OptionsFlowHandler as SilamPollenOptionsFlow
from .coordinator import SilamCoordinator
from .migration import async_migrate_entry  # ядро вызовет при необходимости

# Актуальная версия схемы записи ConfigEntry
CONFIG_VERSION = 3

_LOGGER = logging.getLogger(__name__)

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

    # Если сервис уже существует (hot-reload custom_component) — повторно не создаём
    if hass.services.has_service(DOMAIN, "manual_update"):
        return True

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

    async def handle_manual_update(call):
        """Обработчик ручного обновления выбранных устройств/сущностей."""
        updated_data: dict[str, dict] = {}

        targets = call.data.get("targets", {})
        device_ids = targets.get("device_id", [])
        entity_ids = targets.get("entity_id", [])

        if not device_ids and not entity_ids:
            _LOGGER.warning("manual_update: цели не заданы")
            return {"updated_entries": updated_data} if call.return_response else None

        device_registry = async_get_device_registry(hass)
        registry = er.async_get(hass)

        async def _refresh(entry_id: str) -> None:
            """Запросить немедленное обновление у нужного координатора."""
            coordinator: SilamCoordinator | None = hass.data.get(DOMAIN, {}).get(entry_id)
            if coordinator:
                await coordinator.async_request_refresh()
                # _base_device_name — приватный атрибут; переедет в public-property позже
                updated_data.setdefault(
                    coordinator._base_device_name, coordinator.merged_data  # noqa: SLF001
                )
            else:
                _LOGGER.error("Координатор для записи %s не найден", entry_id)

        # ---------- Обработка устройств ----------
        for dev_id in device_ids:
            dev_entry = device_registry.async_get(dev_id)
            if not dev_entry:
                _LOGGER.error("Устройство %s не найдено", dev_id)
                continue
            for domain, entry_id in dev_entry.identifiers:
                if domain == DOMAIN:
                    await _refresh(entry_id)

        # ---------- Обработка сущностей ----------
        for ent_id in entity_ids:
            ent_entry = registry.async_get(ent_id)
            if not ent_entry or not ent_entry.device_id:
                _LOGGER.error("Сущность %s не связана с устройством", ent_id)
                continue
            dev_entry = device_registry.async_get(ent_entry.device_id)
            if not dev_entry:
                _LOGGER.error("Устройство для сущности %s не найдено", ent_id)
                continue
            for domain, entry_id in dev_entry.identifiers:
                if domain == DOMAIN:
                    await _refresh(entry_id)

        # Возвращаем данные только если вызов сделан с return_response=True
        return {"updated_entries": updated_data} if call.return_response else None

    # Пока оставляем «старую» схему: device_id / entity_id
    hass.services.async_register(
        DOMAIN,
        "manual_update",
        handle_manual_update,
        schema=vol.Schema(
            {
                vol.Required("targets"): {
                    vol.Optional("device_id"): vol.All(cv.ensure_list, [str]),
                    vol.Optional("entity_id"): vol.All(cv.ensure_list, [str]),
                }
            }
        ),
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
    # Важно: не добавляем устаревшие BASE_URL_V5_9_1 / BASE_URL_V6_0 — они будут удалены.
    candidates: list[str] = []
    try:
        from . import const as _const  # локальный импорт, чтобы не плодить циклы
        for _name in (
            "BASE_URL_HIRES_V6_1",
            "BASE_URL_REGIONAL_V5_9_1",
            "BASE_URL_EUROPE_V6_1",
            "BASE_URL_EUROPE_V6_0",
        ):
            _v = getattr(_const, _name, None)
            if isinstance(_v, str) and _v and _v not in candidates:
                candidates.append(_v)
    except Exception:
        # Если по какой-то причине не смогли собрать кандидатов — не падаем,
        # координатор хотя бы получит текущий base_url ниже.
        pass

    # Гарантируем, что текущий base_url есть в списке (на случай кастомных/будущих URL).
    if isinstance(base_url, str) and base_url and base_url not in candidates:
        candidates.insert(0, base_url)

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
    )
    await coordinator.async_config_entry_first_refresh()

    # Сохраняем координатор для последующего доступа
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Подключаем платформы
    platforms = ["sensor", "weather"]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Слушатель изменений опций
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass, entry):
    """Выключить платформы и убрать координатор при удалении записи."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "weather")
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True


async def update_listener(hass, entry):
    """Удалить устаревшие сущности после изменения опций и перезагрузить запись."""
    registry = er.async_get(hass)

    # Опции/данные
    var_list = entry.options.get("var", entry.data.get("var", []))
    forecast_enabled = entry.options.get("forecast", entry.data.get("forecast", False))
    legacy_enabled = entry.options.get("legacy", entry.data.get("legacy", True))

    # Ожидаемые unique_id
    expected_ids: set[str] = {f"{entry.entry_id}_fetch_duration"}

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

            # NOTE: у тебя этот блок был закомментирован — оставляю так же.
            # persistent_notification_async_create(
            #     hass,
            #     (
            #         f"Сущность {entity.entity_id} удалена, "
            #         "так как выбранный тип пыльцы или опции были изменены."
            #     ),
            #     title="SILAM Pollen",
            # )

    await hass.config_entries.async_reload(entry.entry_id)


async def async_get_options_flow(config_entry):
    """Вернуть обработчик Options Flow."""
    return SilamPollenOptionsFlow()
