import logging
from datetime import datetime, timedelta
import aiohttp
import xml.etree.ElementTree as ET

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_NAME

_LOGGER = logging.getLogger(__name__)

# Шаблон URL для запроса данных.
# Параметр времени фиксирован как "present", чтобы получать актуальные данные.
URL_TEMPLATE = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd?var={var}&latitude={latitude}&longitude={longitude}"
    "&time=present&accept=xml"
)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настройка сенсора через config entry.

    Из конфигурационной записи извлекаются параметры:
      - altitude: желаемая высота, к которой выбирается ближайший измеренный уровень.
          Если не указана, используется значение из hass.config.elevation.
      - manual_coordinates: флаг, указывающий, использовать ли ручной ввод координат.
      - latitude, longitude: координаты, если ручной ввод активирован.
      - var: выбранная переменная.
      - update_interval: интервал опроса в минутах.
      
    Теперь имя сенсора берется из entry.title, который устанавливается в config_flow,
    например "SILAM Pollen Alder".
    """
    # Используем entry.title, чтобы имя сенсора соответствовало выбранному аллергену.
    name = entry.title  
    # Получаем высоту из записи, если она задана, иначе используем встроенную высоту HA.
    altitude = entry.data.get("altitude")
    if altitude in (None, "", 0):
        altitude = hass.config.elevation
        _LOGGER.debug("Используем встроенную высоту из hass.config.elevation: %s", altitude)
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    var = entry.data.get("var", "cnc_POLLEN_BIRCH_m22")
    update_interval_minutes = entry.data.get("update_interval", 5)

    sensor = SilamPollenSensor(
        name, hass, altitude, manual_coordinates, manual_latitude, manual_longitude, var
    )
    async_add_entities([sensor], True)

    interval = timedelta(minutes=update_interval_minutes)
    sensor.async_unsub_update = async_track_time_interval(hass, sensor.async_update, interval)

class SilamPollenSensor(Entity):
    def __init__(self, name, hass, altitude, manual_coordinates, manual_latitude, manual_longitude, var):
        """
        Инициализация сенсора.
        
        :param name: Имя сенсора.
        :param hass: Экземпляр Home Assistant.
        :param altitude: Желаемая высота для выбора ближайшего stationFeature.
                         Если не указана, используется значение из hass.config.elevation.
        :param manual_coordinates: Флаг для использования ручного ввода координат.
        :param manual_latitude: Ручная широта, если используется ручной ввод.
        :param manual_longitude: Ручная долгота, если используется ручной ввод.
        :param var: Выбранная переменная для запроса.
        """
        self._state = None
        self._extra_attributes = {}
        self._name = name
        self._hass = hass
        self._altitude = altitude
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._var = var

    @property
    def name(self):
        """Возвращает имя сенсора."""
        return self._name

    @property
    def state(self):
        """Основное состояние сенсора – значение пыльцы."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты сенсора (дата измерения и высота измерения)."""
        return self._extra_attributes

    async def async_update(self, now=None):
        """
        Метод обновления сенсора.
        
        Вызывает fetch_data для получения данных, затем обновляет состояние и дополнительные атрибуты.
        """
        data = await self.fetch_data()
        if data:
            self._state = data.get("pollen_value")
            self._extra_attributes["measurement_date"] = data.get("measurement_date")
            self._extra_attributes["measurement_altitude"] = data.get("measurement_altitude")
        else:
            _LOGGER.error("Не удалось получить или обработать XML данные")

    async def fetch_data(self):
        """
        Формирует URL, выполняет HTTP-запрос, парсит XML и выбирает stationFeature с высотой,
        наиболее близкой к желаемой.
        
        Процесс:
          1. Определяются координаты:
             - Если ручной ввод активирован, используются введённые значения.
             - Иначе берутся координаты из состояния 'zone.home'.
          2. URL формируется на основе шаблона с фиксированным временем "present".
          3. Выполняется HTTP-запрос.
          4. Полученный XML парсится, и из всех stationFeature выбирается тот, у которого атрибут "altitude"
             наиболее близок к желаемой высоте.
          5. Из выбранного stationFeature извлекаются:
             - Значение пыльцы из тега <data> с атрибутом name равным var.
             - Дата измерения (атрибут date).
             - Высота измерения (атрибут altitude).
        """
        try:
            var = self._var

            # Определяем координаты: используем ручные, если активированы, иначе берем из zone.home.
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
            
            # Формирование URL с фиксированным временем "present"
            final_url = URL_TEMPLATE.format(
                var=var,
                latitude=latitude,
                longitude=longitude,
                time="present"
            )
            _LOGGER.debug("Формируем URL: %s", final_url)

            # Выполняем HTTP-запрос
            async with aiohttp.ClientSession() as session:
                async with session.get(final_url) as response:
                    if response.status != 200:
                        _LOGGER.error("Ошибка HTTP запроса: %s", response.status)
                        return None
                    text = await response.text()
                    root = ET.fromstring(text)

                    # Получаем все элементы stationFeature из XML
                    station_features = root.findall(".//stationFeature")
                    if not station_features:
                        _LOGGER.error("Нет stationFeature в XML")
                        return None

                    # Пробуем преобразовать желаемую высоту в число.
                    try:
                        desired_altitude = float(self._altitude)
                    except (TypeError, ValueError):
                        _LOGGER.debug("Желаемая высота не задана или некорректна, выбираем первый элемент")
                        desired_altitude = None

                    best_feature = None
                    if desired_altitude is not None:
                        best_diff = None
                        for sf in station_features:
                            alt_attr = sf.get("altitude")
                            if alt_attr is None:
                                continue
                            try:
                                alt_value = float(alt_attr)
                            except ValueError:
                                continue
                            diff = abs(alt_value - desired_altitude)
                            if best_diff is None or diff < best_diff:
                                best_diff = diff
                                best_feature = sf
                    else:
                        best_feature = station_features[0]

                    if best_feature is None:
                        _LOGGER.error("Не найден подходящий stationFeature")
                        return None

                    # Из выбранного stationFeature извлекаем значение пыльцы
                    data_element = best_feature.find(".//data[@name='{0}']".format(var))
                    if data_element is not None:
                        pollen_value = float(data_element.text)
                    else:
                        _LOGGER.error("Элемент <data name='%s'> не найден в выбранном stationFeature", var)
                        return None

                    # Получаем дополнительные атрибуты: дату измерения и высоту stationFeature
                    measurement_date = best_feature.get("date")
                    measurement_altitude = best_feature.get("altitude")

                    return {
                        "pollen_value": pollen_value,
                        "measurement_date": measurement_date,
                        "measurement_altitude": measurement_altitude
                    }
        except Exception as e:
            _LOGGER.error("Ошибка при получении или обработке XML: %s", e)
            return None
