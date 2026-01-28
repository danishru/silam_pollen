import logging
import aiohttp
import async_timeout

from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, config_entry):
    """
    Миграция ConfigEntry для SILAM Pollen.

    Цели этой миграции (при обновлении интеграции):
      - Для ВСЕХ существующих записей принудительно:
        * legacy = False (устаревший index-сенсор выключаем по умолчанию)
        * version = "smart" (политика выбора датасета по умолчанию — SMART)
      - Автоматически удалить устаревшую сущность index из entity registry.

    Дополнительно (как и раньше):
      - base_url: если отсутствует — пытаемся подобрать из актуальных констант (если они есть).
      - forecast: по умолчанию False, если отсутствует.
      - unique_id: если отсутствует, формируется на основе координат.

    Важно:
      - Все URL-кандидаты берём через getattr из const.py, чтобы можно было безопасно удалить старые константы.
      - Для отображения в UI мы обновляем И data, И options (Options Flow берёт приоритет из options).
    """

    new_data = dict(config_entry.data)
    new_options = dict(config_entry.options)

    # Префикс логов как в координаторе: [<имя службы>]
    # Пытаемся извлечь "человеческое" имя; fallback — title/entry_id.
    base_device_name = (
        new_data.get("base_device_name")
        or new_data.get("name")
        or getattr(config_entry, "title", None)
        or config_entry.entry_id
    )
    log_prefix = f"[{base_device_name}]"

    _LOGGER.debug(
        "%s Starting migration for entry %s: version %s, minor_version %s",
        log_prefix,
        config_entry.entry_id,
        config_entry.version,
        config_entry.minor_version,
    )

    # Текущий minor записи (что уже было применено ранее)
    current_minor = int(config_entry.minor_version or 0)

    # Чистая модель миграции: за один шаг приводим запись к version=3 / minor_version=4.
    target_version = 3
    target_minor_version = 4

    # ---------------------------------------------------------------------
    # ВАЖНО: "принудительные фиксы" (SMART + legacy=False) делаем ТОЛЬКО ОДИН РАЗ
    # при переходе на minor_version=4 (то есть если current_minor < 4).
    # Если уже >=4 — НЕ трогаем выбор пользователя и не перетираем настройки.
    # ---------------------------------------------------------------------
    do_force_defaults_v4 = current_minor < target_minor_version

    # ---------------------------------------------------------------------
    # Достаём актуальные URL-кандидаты из const.py (без жёстких импортов).
    # ---------------------------------------------------------------------
    try:
        from . import const as _const
    except Exception:
        _const = None

    def _get_const_url(name: str):
        if _const is None:
            return None
        v = getattr(_const, name, None)
        return v if isinstance(v, str) and v else None

    # 1) base_url — автоподбор по отклику API, если отсутствует
    if "base_url" not in new_data:
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")
        chosen_url = None

        # В порядке приоритета (актуальные наборы)
        url_candidates = [
            _get_const_url("BASE_URL_HIRES_V6_1"),
            _get_const_url("BASE_URL_REGIONAL_V5_9_1"),
            _get_const_url("BASE_URL_EUROPE_V6_1"),
            _get_const_url("BASE_URL_EUROPE_V6_0"),
        ]
        url_candidates = [u for u in url_candidates if u]

        if latitude is not None and longitude is not None and url_candidates:
            async with aiohttp.ClientSession() as session:
                for url in url_candidates:
                    # Лёгкий пробный запрос, чтобы убедиться, что endpoint живой.
                    # Используем NCSS-стиль (time_start/time_duration), чтобы не зависеть от WMS "time=present".
                    test_url = (
                        f"{url}?var=POLI&latitude={latitude}&longitude={longitude}"
                        f"&time_start=present&time_duration=PT0H&accept=xml"
                    )
                    try:
                        async with async_timeout.timeout(10):
                            async with session.get(test_url) as response:
                                _ = await response.text()
                                if response.status == 200:
                                    chosen_url = url
                                    _LOGGER.debug("%s URL %s passed probe (HTTP 200)", log_prefix, url)
                                    break
                                _LOGGER.debug("%s URL %s returned HTTP %s", log_prefix, url, response.status)
                    except Exception as err:
                        _LOGGER.debug("%s Error probing URL %s: %s", log_prefix, url, err)
        else:
            _LOGGER.debug("%s Coordinates missing or no URL candidates available; skipping URL probing.", log_prefix)

        # Fallback: если ничего не выбрали — берём первый кандидат (если есть)
        if chosen_url is None and url_candidates:
            chosen_url = url_candidates[0]
            _LOGGER.debug("%s No URL responded with HTTP 200; falling back to %s", log_prefix, chosen_url)

        if chosen_url:
            new_data["base_url"] = chosen_url
            _LOGGER.debug("%s Selected base URL: %s", log_prefix, chosen_url)

    # 2) forecast — по умолчанию False, если отсутствует
    if "forecast" not in new_data:
        new_data["forecast"] = False

    # 3) unique_id — если отсутствует, задаём на основе координат
    if new_data.get("unique_id") is None:
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")
        if latitude is not None and longitude is not None:
            unique_id = f"{latitude}_{longitude}"
            new_data["unique_id"] = unique_id
            _LOGGER.debug("%s Set unique_id: %s", log_prefix, unique_id)

    # ---------------------------------------------------------------------
    # ОДНОРАЗОВОЕ ПРИНУДИТЕЛЬНОЕ ИЗМЕНЕНИЕ (только при current_minor < 4)
    # ---------------------------------------------------------------------
    if do_force_defaults_v4:
        prev_v_data = new_data.get("version")
        prev_v_opt = new_options.get("version")
        if prev_v_data != "smart":
            new_data["version"] = "smart"
            _LOGGER.debug("%s Forced data version='smart' (was %s).", log_prefix, prev_v_data)
        if prev_v_opt != "smart":
            new_options["version"] = "smart"
            _LOGGER.debug("%s Forced options version='smart' (was %s).", log_prefix, prev_v_opt)

        prev_l_data = new_data.get("legacy")
        prev_l_opt = new_options.get("legacy")
        if prev_l_data is not False:
            new_data["legacy"] = False
            _LOGGER.debug("%s Forced data legacy=False (was %s).", log_prefix, prev_l_data)
        if prev_l_opt is not False:
            new_options["legacy"] = False
            _LOGGER.debug("%s Forced options legacy=False (was %s).", log_prefix, prev_l_opt)

    # ---------------------------------------------------------------------
    # НОВОЕ: автоматически удаляем устаревший сенсор index из entity registry
    # unique_id у него: f"{config_entry.entry_id}_index"
    # ---------------------------------------------------------------------
    try:
        registry = er.async_get(hass)
        legacy_index_unique_id = f"{config_entry.entry_id}_index"

        for ent in list(registry.entities.values()):
            if ent.config_entry_id != config_entry.entry_id:
                continue
            if ent.unique_id == legacy_index_unique_id:
                _LOGGER.debug(
                    "%s Removing deprecated legacy index entity: %s (unique_id=%s)",
                    log_prefix,
                    ent.entity_id,
                    ent.unique_id,
                )
                registry.async_remove(ent.entity_id)
    except Exception as err:
        # Миграция не должна падать из-за удаления сущности
        _LOGGER.debug("%s Failed to remove deprecated legacy index entity: %s", log_prefix, err)

    # Фиксируем, что эта миграция применена (version/minor)
    new_minor_version = target_minor_version

    # ---------------------------------------------------------------------
    # No-op guard: не обновляем запись, если ничего не изменилось
    # (чтобы не провоцировать повторные миграции/перезагрузки и лог-спам).
    # ---------------------------------------------------------------------
    changed = (
        new_data != config_entry.data
        or new_options != config_entry.options
        or int(config_entry.minor_version or 0) != new_minor_version
        or config_entry.version != target_version
    )

    if not changed:
        _LOGGER.debug("%s Migration no-op for entry %s (no changes).", log_prefix, config_entry.entry_id)
        return True

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        options=new_options,
        minor_version=new_minor_version,
        version=target_version,
    )

    _LOGGER.debug("%s Migration successful, new data: %s", log_prefix, new_data)
    _LOGGER.debug("%s Migration successful, new options: %s", log_prefix, new_options)
    return True
