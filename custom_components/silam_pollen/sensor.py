import logging
from datetime import datetime, timedelta
import aiohttp
import xml.etree.ElementTree as ET

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настройка сенсора через config entry.
    Получаем параметры:
      - data_url: шаблон URL,
      - altitude: высота (vertCoord), по умолчанию 275,
      - manual_coordinates: флаг, использовать ли ручные координаты,
      - latitude, longitude: значения координат (при ручном вводе),
      - var: выбранная переменная из списка,
      - update_interval: интервал опроса в минутах.
    """
    name = entry.data.get(CONF_NAME, "SILAM Pollen (XML)")
    data_url_template = entry.data.get("data_url")
    altitude = entry.data.get("altitude", 275)
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    var = entry.data.get("var", "cnc_POLLEN_BIRCH_m22")
    update_interval_minutes = entry.data.get("update_interval", 5)

    sensor = SilamPollenSensor(
        name, hass, data_url_template, altitude,
        manual_coordinates, manual_latitude, manual_longitude, var
    )
    async_add_entities([sensor], True)

    # Планируем опрос сенсора с интервалом, выбранным пользователем
    interval = timedelta(minutes=update_interval_minutes)
    sensor.async_unsub_update = async_track_time_interval(hass, sensor.async_update, interval)

class SilamPollenSensor(Entity):
    def __init__(self, name, hass, data_url_template, altitude,
                 manual_coordinates, manual_latitude, manual_longitude, var):
        """
        Инициализация сенсора.
        
        :param name: имя сенсора.
        :param hass: экземпляр Home Assistant.
        :param data_url_template: строка-шаблон URL с плейсхолдерами.
        :param altitude: высота (vertCoord), по умолчанию 275.
        :param manual_coordinates: флаг, использовать ли ручные координаты.
        :param manual_latitude: вручную заданная широта.
        :param manual_longitude: вручную заданная долгота.
        :param var: выбранная переменная для запроса.
        """
        self._state = None
        self._name = name
        self._hass = hass
        self._data_url_template = data_url_template
        self._altitude = altitude
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._var = var

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    async def async_update(self, now=None):
        data = await self.fetch_data()
        if data:
            self._state = data.get("pollen_value")
        else:
            _LOGGER.error("Не удалось получить или обработать XML данные")

    async def fetch_data(self):
        """
        Формирует URL на основе настроек и выполняет HTTP-запрос.
        Извлекает значение из тега <data ...> с именем var.
        """
        try:
            # Используем выбранную переменную
            var = self._var

            # Определяем координаты:
            if self._manual_coordinates and self._manual_latitude is not None and self._manual_longitude is not None:
                latitude = self._manual_latitude
                longitude = self._manual_longitude
            else:
                zone = self._hass.states.get("zone.home")
                if zone is None:
                    _LOGGER.error("Зона 'home' не найдена")
                    return None
                latitude = zone.attributes.get("latitude")
                longitude = zone.attributes.get("longitude")
            
            # Используем текущее время в формате ISO с указанием часового пояса Z
            time_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            vertCoord = self._altitude

            # Формирование окончательного URL
            final_url = self._data_url_template.format(
                var=var,
                latitude=latitude,
                longitude=longitude,
                time=time_str,
                vertCoord=vertCoord
            )
            _LOGGER.debug("Формируем URL: %s", final_url)

            async with aiohttp.ClientSession() as session:
                async with session.get(final_url) as response:
                    if response.status != 200:
                        _LOGGER.error("Ошибка HTTP запроса: %s", response.status)
                        return None
                    text = await response.text()
                    root = ET.fromstring(text)
                    # Извлекаем значение из тега <data ...> с атрибутом name равным var
                    data_element = root.find(".//data[@name='{0}']".format(var))
                    if data_element is not None:
                        return {"pollen_value": float(data_element.text)}
                    else:
                        _LOGGER.error("Элемент <data name='%s'> не найден в XML", var)
                        return None
        except Exception as e:
            _LOGGER.error("Ошибка при получении или обработке XML: %s", e)
            return None
