import logging
import aiohttp
import async_timeout

from .const import BASE_URL_V5_9_1, BASE_URL_V6_0

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, config_entry):
    """
    Мигрирует старую запись, добавляя недостающие поля и поднимая версию/минор:
      - base_url: проверяет доступность API по BASE_URL_V5_9_1 и BASE_URL_V6_0,
                  выбирает ответивший 200, иначе берёт BASE_URL_V6_0.
      - forecast: по умолчанию False, если отсутствует.
      - unique_id: если отсутствует, формируется на основе координат.
      - legacy: по умолчанию True для существующих записей (мягкий вывод из эксплуатации сводного индекса).

    При установке legacy для существующих записей поднимаем minor_version до 3.
    """

    _LOGGER.debug(
        "Starting migration for entry %s: version %s, minor_version %s",
        config_entry.entry_id,
        config_entry.version,
        config_entry.minor_version,
    )

    new_data = dict(config_entry.data)

    # Базовый расчёт целевого minor_version
    new_minor_version = int(config_entry.minor_version or 0)
    if config_entry.version == 1 and new_minor_version < 2:
        # Старый формат → фиксируем предыдущую миграцию как минимум 2
        new_minor_version = 2

    # 1) base_url — автоподбор по отклику API, если отсутствует
    if "base_url" not in new_data:
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")
        chosen_url = None

        if latitude is not None and longitude is not None:
            urls = [BASE_URL_V5_9_1, BASE_URL_V6_0]
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    test_url = (
                        f"{url}?var=POLI&latitude={latitude}&longitude={longitude}"
                        f"&time=present&accept=xml"
                    )
                    try:
                        async with async_timeout.timeout(10):
                            async with session.get(test_url) as response:
                                text = await response.text()
                                if response.status == 200:
                                    chosen_url = url
                                    _LOGGER.debug("URL %s passed probe (HTTP 200)", url)
                                    break
                                else:
                                    _LOGGER.debug(
                                        "URL %s returned status %s: %s",
                                        url,
                                        response.status,
                                        text,
                                    )
                    except Exception as err:
                        _LOGGER.debug("Error probing URL %s: %s", url, err)
        else:
            _LOGGER.debug("Coordinates are missing in entry; skipping URL probing.")

        if chosen_url is None:
            _LOGGER.debug(
                "No URL responded with HTTP 200; falling back to BASE_URL_V6_0"
            )
            chosen_url = BASE_URL_V6_0

        new_data["base_url"] = chosen_url
        _LOGGER.debug("Selected base URL: %s", chosen_url)

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
            _LOGGER.debug("Set unique_id: %s", unique_id)

    # 4) legacy — для существующих записей включаем по умолчанию
    #    (гарантируем наличие ключа в data, чтобы мягко выводить сводный индекс из эксплуатации)
    if "legacy" not in new_data:
        new_data["legacy"] = True
        # фиксация этой миграции отдельным минором
        if new_minor_version < 3:
            new_minor_version = 3
        _LOGGER.debug("Added legacy=True flag for existing entry.")

    # Поднимаем основную версию записи до актуальной (CONFIG_VERSION == 3)
    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        minor_version=new_minor_version,
        version=3,
    )
    _LOGGER.debug("Migration successful, new data: %s", new_data)
    return True