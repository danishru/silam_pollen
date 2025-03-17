import logging
import aiohttp
import async_timeout

from .const import BASE_URL_V5_9_1, BASE_URL_V6_0

_LOGGER = logging.getLogger(__name__)

async def async_migrate_entry(hass, config_entry):
    """
    Мигрирует старую запись, добавляя поле 'base_url' с проверкой доступности API.
    Функция перебирает BASE_URL_V5_9_1 и BASE_URL_V6_0 с использованием координат из записи.
    Если один из URL возвращает статус 200, выбирается он, иначе – устанавливается значение по умолчанию (BASE_URL_V6_0).
    """
    _LOGGER.debug("Начало миграции записи %s: версия %s, minor_version %s",
                  config_entry.entry_id, config_entry.version, config_entry.minor_version)
    
    new_data = dict(config_entry.data)
    
    # Если поле base_url отсутствует, выполняем тестирование URL
    if "base_url" not in new_data:
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")
        chosen_url = None

        if latitude is not None and longitude is not None:
            urls = [BASE_URL_V5_9_1, BASE_URL_V6_0]
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    test_url = f"{url}?var=POLI&latitude={latitude}&longitude={longitude}&time=present&accept=xml"
                    try:
                        async with async_timeout.timeout(10):
                            async with session.get(test_url) as response:
                                text = await response.text()
                                if response.status == 200:
                                    chosen_url = url
                                    _LOGGER.debug("URL %s успешно прошёл тест (HTTP 200)", url)
                                    break
                                else:
                                    _LOGGER.debug("URL %s вернул статус %s: %s", url, response.status, text)
                    except Exception as err:
                        _LOGGER.debug("Ошибка при тестировании URL %s: %s", url, err)
        else:
            _LOGGER.debug("Координаты не заданы в записи, пропускаем тестирование URL.")

        if chosen_url is None:
            _LOGGER.debug("Не найдено ни одного URL с ответом 200, устанавливаем значение по умолчанию BASE_URL_V6_0")
            chosen_url = BASE_URL_V6_0

        new_data["base_url"] = chosen_url
        _LOGGER.debug("Выбранный базовый URL: %s", chosen_url)
        
    # Устанавливаем опцию прогноза по умолчанию, если она не задана
    if "forecast" not in new_data:
        new_data["forecast"] = False
    
    # Обновляем запись с новой информацией
    hass.config_entries.async_update_entry(
        config_entry, data=new_data, minor_version=1, version=config_entry.version
    )
    _LOGGER.debug("Миграция успешна, новые данные: %s", new_data)
    return True
