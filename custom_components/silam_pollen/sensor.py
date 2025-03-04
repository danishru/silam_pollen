import logging
from datetime import datetime, timedelta
import aiohttp
import xml.etree.ElementTree as ET

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType

# Определяем домен интеграции
DOMAIN = "silam_pollen"

_LOGGER = logging.getLogger(__name__)

# Шаблон URL для запроса данных.
# Передаются три параметра var: основной (из настроек), а также POLI и POLISRC.
# Время фиксированное ("present").
URL_TEMPLATE = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd?var={var}&var=POLI&var=POLISRC&latitude={latitude}&longitude={longitude}"
    "&time=present&accept=xml"
)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настройка интеграции через config entry.

    Из записи извлекаются:
      - altitude: желаемая высота (если не задана, берется из hass.config.elevation)
      - manual_coordinates, latitude, longitude: параметры для координат (при ручном вводе)
      - var: выбранная переменная (например, "cnc_POLLEN_ALDER_m22")
      - update_interval: интервал опроса в минутах

    Имя устройства (base_device_name) формируется в config_flow и хранится в entry.title,
    например, "SILAM Pollen Alder". Создаются три сенсора с разными типами, которые объединяются
    в одно устройство по entry.entry_id.
    """
    base_device_name = entry.title  # Общее имя устройства
    altitude = entry.data.get("altitude")
    if altitude in (None, "", 0):
        altitude = hass.config.elevation
        _LOGGER.debug("Используем встроенную высоту из hass.config.elevation: %s", altitude)
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    var = entry.data.get("var", "cnc_POLLEN_ALDER_m22")
    update_interval_minutes = entry.data.get("update_interval", 5)

    sensors = [
        # Основной сенсор
        SilamPollenSensor(
            sensor_name=base_device_name,
            base_device_name=base_device_name,
            hass=hass,
            altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
            var=var,
            entry_id=entry.entry_id,
            sensor_type="main"
        ),
        # Сенсор для Pollen Index
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Pollen Index",
            base_device_name=base_device_name,
            hass=hass,
            altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
            var=var,
            entry_id=entry.entry_id,
            sensor_type="pollen_index"
        ),
        # Сенсор для Responsible Elevated
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Responsible Elevated",
            base_device_name=base_device_name,
            hass=hass,
            altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
            var=var,
            entry_id=entry.entry_id,
            sensor_type="responsible_elevated"
        ),
    ]

    async_add_entities(sensors, True)
    interval = timedelta(minutes=update_interval_minutes)
    for sensor in sensors:
        sensor.async_unsub_update = async_track_time_interval(hass, sensor.async_update, interval)

class SilamPollenSensor(Entity):
    def __init__(self, sensor_name, base_device_name, hass, altitude, manual_coordinates,
                 manual_latitude, manual_longitude, var, entry_id, sensor_type):
        """
        Инициализация сенсора.

        :param sensor_name: Индивидуальное имя сенсора (например, "SILAM Pollen Alder Pollen Index").
        :param base_device_name: Общее имя устройства (например, "SILAM Pollen Alder") для объединения сенсоров.
        :param hass: Экземпляр Home Assistant.
        :param altitude: Желательная высота.
        :param manual_coordinates: Флаг ручного ввода координат.
        :param manual_latitude: Ручная широта.
        :param manual_longitude: Ручная долгота.
        :param var: Выбранная переменная (например, "cnc_POLLEN_ALDER_m22").
        :param entry_id: Уникальный идентификатор config entry для объединения сенсоров.
        :param sensor_type: Тип сенсора: "main", "pollen_index" или "responsible_elevated".
        """
        self._state = None
        self._extra_attributes = {}
        self._name = sensor_name
        self._base_device_name = base_device_name  # Общее имя для всех сенсоров
        self._hass = hass
        self._altitude = altitude
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._var = var
        self._entry_id = entry_id
        self._sensor_type = sensor_type

        # Устанавливаем _attr_device_info для объединения всех сенсоров в одно устройство.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_device_name,  # Общее имя устройства, например "SILAM Pollen Alder"
            manufacturer="SILAM",
            model="SILAM Pollen Sensor",
            sw_version="0.1.0-beta",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://silam.fmi.fi/pollen.html?region=europe"
        )

    @property
    def name(self):
        """Возвращает имя сенсора."""
        return self._name

    @property
    def unique_id(self):
        """Возвращает уникальный идентификатор сенсора для управления через UI."""
        return f"{self._entry_id}_{self._sensor_type}"

    @property
    def state(self):
        """Возвращает основное состояние сенсора."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Возвращает дополнительные атрибуты сенсора."""
        return self._extra_attributes

    async def async_update(self, now=None):
        """
        Обновляет данные сенсора.
        В зависимости от sensor_type выбирается соответствующее значение из fetch_data.
        """
        data = await self.fetch_data()
        if data:
            if self._sensor_type == "main":
                self._state = data.get("main", {}).get("pollen_value")
                self._extra_attributes.update(data.get("main", {}))
            elif self._sensor_type == "pollen_index":
                self._state = data.get("pollen_index")
            elif self._sensor_type == "responsible_elevated":
                self._state = data.get("responsible_elevated")
        else:
            _LOGGER.error("Не удалось получить или обработать XML данные")

    async def fetch_data(self):
        """
        Выполняет HTTP-запрос и парсит XML, возвращая данные для всех сенсоров.

        Процесс:
          1. Определяются координаты (ручной ввод или из zone.home).
          2. Формируется URL с фиксированным временем "present" и тремя параметрами var.
          3. Выполняется запрос, XML разбирается.
          4. Для основного сенсора выбирается stationFeature с высотой, наиболее близкой к желаемой,
             извлекаются pollen_value, measurement_date и measurement_altitude.
          5. Из дополнительного блока извлекаются значения для POLI (pollen_index) и POLISRC (responsible_elevated).
        """
        try:
            var = self._var

            # Определяем координаты: если ручной ввод активирован, используем введённые значения; иначе – из zone.home.
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
            
            # Формируем URL с фиксированным временем "present"
            final_url = URL_TEMPLATE.format(
                var=var,
                latitude=latitude,
                longitude=longitude,
                time="present"
            )
            _LOGGER.debug("Формируем URL: %s", final_url)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(final_url) as response:
                    if response.status != 200:
                        _LOGGER.error("Ошибка HTTP запроса: %s", response.status)
                        return None
                    text = await response.text()
                    root = ET.fromstring(text)
                    
                    # Данные для основного сенсора
                    main_collection = root.find(".//stationProfileFeatureCollection")
                    main_data = {}
                    if main_collection is not None:
                        station_features = main_collection.findall(".//stationFeature")
                        if station_features:
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
                            
                            if best_feature is not None:
                                data_element = best_feature.find(".//data[@name='{0}']".format(self._var))
                                if data_element is not None:
                                    main_data["pollen_value"] = float(data_element.text)
                                main_data["measurement_date"] = best_feature.get("date")
                                main_data["measurement_altitude"] = best_feature.get("altitude")
                    
                    # Данные для дополнительных сенсоров из второго блока
                    additional_collection = root.find(".//stationFeatureCollection")
                    additional_data = {}
                    if additional_collection is not None:
                        additional_feature = additional_collection.find(".//stationFeature")
                        if additional_feature is not None:
                            poli_elem = additional_feature.find(".//data[@name='POLI']")
                            polisrc_elem = additional_feature.find(".//data[@name='POLISRC']")
                            if poli_elem is not None:
                                additional_data["pollen_index"] = float(poli_elem.text)
                            if polisrc_elem is not None:
                                additional_data["responsible_elevated"] = float(polisrc_elem.text)
                    
                    return {
                        "main": main_data,
                        "pollen_index": additional_data.get("pollen_index"),
                        "responsible_elevated": additional_data.get("responsible_elevated")
                    }
        except Exception as e:
            _LOGGER.error("Ошибка при получении или обработке XML: %s", e)
            return None
