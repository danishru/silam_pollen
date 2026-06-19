import logging
import aiohttp
import async_timeout

from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, config_entry):
    """
    Миграция ConfigEntry для SILAM Pollen.

    Цели миграций:
      - До minor_version=4 однократно:
        * legacy = False (устаревший index-сенсор выключаем по умолчанию)
        * version = "smart" (политика выбора датасета по умолчанию — SMART)
      - До minor_version=5:
        * фиксированный Europe v6.0 заменить на Europe v6.1;
        * фиксированный Regional v5.9.1 заменить на Regional v6.1;
        * SMART-настройки не изменять.
      - Автоматически удалить устаревшую сущность index из entity registry.

    Дополнительно (как и раньше):
      - base_url: если отсутствует — пытаемся подобрать из актуальных датасетов (через DATASETS).
      - forecast: по умолчанию False, если отсутствует.
      - unique_id: если отсутствует, формируется на основе координат.

    Важно:
      - Кандидаты URL берём только из DATASETS (iter_datasets_for_probe + dataset_base_url).
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

    # Чистая модель миграции: за один шаг приводим запись к version=3 / minor_version=5.
    target_version = 3
    target_minor_version = 5

    # ---------------------------------------------------------------------
    # ВАЖНО: "принудительные фиксы" (SMART + legacy=False) делаем ТОЛЬКО ОДИН РАЗ
    # при переходе на minor_version=4 (то есть если current_minor < 4).
    # Если уже >=4 — НЕ трогаем выбор пользователя и не перетираем настройки.
    # ---------------------------------------------------------------------
    do_force_defaults_v4 = current_minor < 4
    do_migrate_fixed_datasets_v5 = current_minor < 5

    # Сохраняем исходный эффективный выбор до миграции 3.4. Это позволяет
    # корректно мигрировать фиксированный legacy-датасет даже при обновлении
    # сразу с minor_version < 4 на minor_version 5.
    selected_version_v5 = new_options.get("version")
    if not selected_version_v5:
        selected_version_v5 = new_data.get("version")

    fixed_dataset_migrations_v5 = {
        # Europe v6.0 -> Europe v6.1
        "sep60": "silam_europe_pollen_v6_1",
        "v6_0": "silam_europe_pollen_v6_1",
        "silam_europe_pollen_v6_0": "silam_europe_pollen_v6_1",
        # Regional v5.9.1 -> Regional v6.1
        "srp591": "silam_regional_pollen_v6_1",
        "v5_9_1": "silam_regional_pollen_v6_1",
        "silam_regional_pollen_v5_9_1": "silam_regional_pollen_v6_1",
    }
    target_dataset_name_v5 = (
        fixed_dataset_migrations_v5.get(selected_version_v5)
        if do_migrate_fixed_datasets_v5
        else None
    )

    # ---------------------------------------------------------------------
    # Достаём актуальные URL-кандидаты из const.py (DATASETS).
    # ---------------------------------------------------------------------
    try:
        from .const import DATASETS, dataset_base_url, iter_datasets_for_probe
    except Exception as err:
        # Без этого миграция не сможет корректно подобрать base_url.
        _LOGGER.error("%s Failed to import DATASETS helpers from const.py: %s", log_prefix, err)
        return False

    def _build_url_candidates() -> list[str]:
        urls: list[str] = []
        for dataset_name in iter_datasets_for_probe():
            u = dataset_base_url(dataset_name)
            if isinstance(u, str) and u and u not in urls:
                urls.append(u)
        return urls

    # 1) base_url — автоподбор по отклику API, если отсутствует
    if "base_url" not in new_data and target_dataset_name_v5 is None:
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")
        chosen_url = None

        # В порядке приоритета (актуальные наборы)
        url_candidates = _build_url_candidates()

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
                    except Exception as probe_err:
                        _LOGGER.debug("%s Error probing URL %s: %s", log_prefix, url, probe_err)
        else:
            _LOGGER.debug("%s Coordinates missing or no URL candidates available; skipping URL probing.", log_prefix)

        # Fallback внутри DATASETS: если ничего не выбрали — берём первый кандидат (если есть)
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
    # МИГРАЦИЯ 3.5: прямые замены устаревших ФИКСИРОВАННЫХ датасетов.
    #
    # Важно:
    # - options["version"] имеет приоритет над data["version"], как в Options Flow;
    # - SMART не трогаем, даже если сохранённый base_url указывает на старый датасет;
    # - режим пользователя сохраняем: fixed остаётся fixed;
    # - сетевой probe не выполняем: это детерминированная замена версии.
    # ---------------------------------------------------------------------
    if do_migrate_fixed_datasets_v5:
        if target_dataset_name_v5 is not None:
            target_meta = DATASETS.get(target_dataset_name_v5)
            if target_meta is None:
                _LOGGER.error(
                    "%s Dataset migration 3.5 failed: target %s is missing.",
                    log_prefix,
                    target_dataset_name_v5,
                )
                return False

            target_version_key = target_meta.src
            target_base_url = dataset_base_url(target_dataset_name_v5)

            previous_base_url = new_data.get("base_url")
            new_data["version"] = target_version_key
            new_options["version"] = target_version_key
            new_data["base_url"] = target_base_url

            _LOGGER.info(
                "%s Migrated fixed dataset %s -> %s (base_url: %s -> %s).",
                log_prefix,
                selected_version_v5,
                target_version_key,
                previous_base_url,
                target_base_url,
            )
        elif selected_version_v5 == "smart":
            _LOGGER.debug(
                "%s Dataset migration 3.5 skipped: selection is SMART.",
                log_prefix,
            )

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
