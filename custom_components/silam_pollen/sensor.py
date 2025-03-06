import logging
import re
from datetime import timedelta
import aiohttp
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from .const import DOMAIN, VAR_OPTIONS

_LOGGER = logging.getLogger(__name__)

# Базовый URL для запроса данных SILAM Pollen
BASE_URL = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd"
)

# Определяем версию SILAM, извлекая её из BASE_URL
match = re.search(r"pollen_v(\d+_\d+)", BASE_URL)
if match:
    SILAM_VERSION = match.group(1)
else:
    SILAM_VERSION = "unknown"

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настройка интеграции через config entry.

    Извлекаются параметры из записи:
      - altitude: высота (если не задана, берется из hass.config.elevation)
      - manual_coordinates, latitude, longitude: координаты (если заданы вручную)
      - var: список типов пыльцы, для которых нужно создать сенсоры
      - update_interval: интервал опроса данных (в минутах)

    Создаются:
      - один "сводный" сенсор (тип "index"), который отображает общие данные,
      - отдельные сенсоры (тип "main") для каждого выбранного типа пыльцы.
      
    При обновлении опций через Options Flow новые значения будут извлекаться из entry.options.
    """
    base_device_name = entry.title

    # Получаем высоту: из записи или из глобальной конфигурации Home Assistant
    altitude = entry.data.get("altitude")
    if altitude in (None, ""):
        altitude = hass.config.elevation
        _LOGGER.debug("Используем высоту из hass.config.elevation: %s", altitude)
    
    # Получаем флаг ручного задания координат и сами координаты (если заданы)
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    
    # Читаем список типов пыльцы и интервал опроса из опций, если они заданы,
    # иначе используем значения из config_entry.data.
    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval_minutes = entry.options.get("update_interval", entry.data.get("update_interval", 5))

    sensors = []
    # Создаем "сводный" сенсор для индекса (тип "index")
    sensors.append(
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Index",
            base_device_name=base_device_name,
            hass=hass,
            altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
            var=var_list,  # для "index" передается список типов пыльцы
            entry_id=entry.entry_id,
            sensor_type="index"
        )
    )
    # Создаем отдельный сенсор для каждого типа пыльцы (тип "main")
    for pollen in var_list:
        translation_key = VAR_OPTIONS.get(pollen, pollen)
        sensors.append(
            SilamPollenSensor(
                sensor_name=f"{base_device_name} {translation_key}",
                base_device_name=base_device_name,
                hass=hass,
                altitude=altitude,
                manual_coordinates=manual_coordinates,
                manual_latitude=manual_latitude,
                manual_longitude=manual_longitude,
                var=pollen,  # для "main" передается конкретный тип пыльцы
                entry_id=entry.entry_id,
                sensor_type="main"
            )
        )

    # Регистрируем новые сенсоры в Home Assistant
    async_add_entities(sensors, True)
    # Настраиваем интервал опроса в соответствии с опцией update_interval
    interval = timedelta(minutes=update_interval_minutes)
    for sensor in sensors:
        sensor.async_unsub_update = async_track_time_interval(hass, sensor.async_update, interval)


class SilamPollenSensor(SensorEntity):
    def __init__(self, sensor_name, base_device_name, hass, altitude, manual_coordinates,
                 manual_latitude, manual_longitude, var, entry_id, sensor_type):
        """
        Инициализация сенсора SILAM Pollen.

        sensor_type:
          - "index": сводный сенсор, обрабатывающий данные из блока stationFeatureCollection.
                     Здесь self._var – список типов пыльцы.
          - "main": сенсор для конкретного типа пыльцы, отображающий pollen_value.
                    Здесь self._var – строка с выбранным типом пыльцы.
                    
        Все сенсоры объединяются в одно устройство (DeviceInfo формируется по entry_id).
        """
        self._state = None
        self._extra_attributes = {}
        self._name = sensor_name
        self._base_device_name = base_device_name
        self._hass = hass
        self._altitude = altitude
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._var = var
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        # Для сенсоров "main" будем получать единицы измерения
        self._unit_of_measurement = None

        sw_version = SILAM_VERSION.replace("_", ".")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_device_name,
            manufacturer="SILAM",
            model="SILAM Pollen Sensor",
            sw_version=sw_version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://silam.fmi.fi/pollen.html?region=europe"
        )
        # Если сенсор "main", задаем ключ перевода для автоматического перевода имени
        if self._sensor_type == "main":
            self._attr_translation_key = VAR_OPTIONS.get(self._var, None)
        else:
            self._attr_translation_key = None

    @property
    def name(self):
        """Возвращает имя сенсора для отображения в интерфейсе Home Assistant."""
        return self._name

    @property
    def unique_id(self):
        # Для сенсора "index" возвращаем постоянный уникальный идентификатор
        if self._sensor_type == "index":
            return f"{self._entry_id}_index"
        # Для сенсора "main" включаем значение var в уникальный идентификатор
        return f"{self._entry_id}_{self._sensor_type}_{self._var}"

    @property
    def native_value(self):
        """
        Возвращает текущее значение сенсора.
        Это значение используется для отображения в интерфейсе.
        """
        return self._state

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты, возвращаемые сенсором."""
        return self._extra_attributes

    @property
    def native_unit_of_measurement(self):
        """
        Возвращает единицы измерения для сенсора "main".
        Для "index" возвращается None.
        """
        if self._sensor_type == "main":
            return self._unit_of_measurement
        return None

    @property
    def suggested_display_precision(self):
        """
        Рекомендуемая точность отображения.
        Для сенсоров "main" возвращается 0 (округление до целых чисел).
        """
        if self._sensor_type == "main":
            return 0
        return None

    def _build_url_index(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсора "index".
        
        Если список типов пыльцы (self._var) не пуст, для каждого типа добавляем параметр.
        Затем добавляются фиксированные параметры: POLI, POLISRC, координаты, время и формат.
        """
        query_params = []
        if self._var and isinstance(self._var, list) and len(self._var) > 0:
            for pollen in self._var:
                query_params.append(f"var={pollen}")
        query_params.append("var=POLI")
        query_params.append("var=POLISRC")
        query_params.append(f"latitude={latitude}")
        query_params.append(f"longitude={longitude}")
        query_params.append("time=present")
        query_params.append("accept=xml")
        return BASE_URL + "?" + "&".join(query_params)

    def _build_url_main(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсора "main".
        
        Здесь используется конкретный тип пыльцы (self._var) и фиксированные параметры.
        """
        query_params = []
        query_params.append(f"var={self._var}")
        query_params.append("var=POLI")
        query_params.append("var=POLISRC")
        query_params.append(f"latitude={latitude}")
        query_params.append(f"longitude={longitude}")
        query_params.append("time=present")
        query_params.append("accept=xml")
        return BASE_URL + "?" + "&".join(query_params)

    async def async_update(self, now=None):
        """
        Обновляет данные сенсора.
        
        Для сенсора "index" извлекается индекс пыльцы и ответственное значение (POLISRC).
        Для сенсора "main" выбирается оптимальный stationFeature по близости к заданной высоте,
        из которого извлекается pollen_value для выбранного типа пыльцы и единицы измерения.
        """
        data = await self.fetch_data()
        if data:
            if self._sensor_type == "index":
                pollen_index = data.get("pollen_index")
                if pollen_index is not None:
                    try:
                        index_value = int(pollen_index)
                    except (ValueError, TypeError):
                        index_value = None
                    # Отображаем индекс пыльцы в виде текстового значения
                    mapping = {
                        1: "VeryLow",
                        2: "Low",
                        3: "Moderate",
                        4: "High",
                        5: "VeryHigh"
                    }
                    self._state = mapping.get(index_value, "Unknown")
                else:
                    self._state = None

                responsible_elevated = data.get("responsible_elevated")
                if responsible_elevated is not None:
                    try:
                        re_value = int(responsible_elevated)
                    except (ValueError, TypeError):
                        re_value = None
                    re_mapping = {
                        -1: "missing",
                        1: "alder",
                        2: "birch",
                        3: "grass",
                        4: "olive",
                        5: "mugwort",
                        6: "ragweed",
                        7: "hazel"
                    }
                    self._extra_attributes["responsible_elevated"] = re_mapping.get(re_value, "Unknown")
                else:
                    self._extra_attributes["responsible_elevated"] = None
            elif self._sensor_type == "main":
                main_data = data.get("main", {})
                self._state = main_data.get("pollen_value")
                self._extra_attributes.update(main_data)
                # Сохраняем единицы измерения для сенсора "main"
                self._unit_of_measurement = main_data.get("unit_of_measurement")
        else:
            _LOGGER.error("Не удалось получить или обработать XML данные")

    async def fetch_data(self):
        """
        Выполняет HTTP-запрос для получения XML-данных, парсит их и возвращает нужные данные.
        
        Логика обработки:
          - Для сенсора "index": используется URL, сформированный через _build_url_index,
            и извлекаются данные из блока stationFeatureCollection.
          - Для сенсора "main": используется URL, сформированный через _build_url_main,
            выбирается оптимальный stationFeature по близости к заданной высоте, 
            и извлекается значение pollen_value для выбранного типа пыльцы.
        """
        try:
            # Определяем координаты: либо вручную заданные, либо из зоны "home"
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
            
            # Формируем URL в зависимости от типа сенсора
            if self._sensor_type == "index":
                final_url = self._build_url_index(latitude, longitude)
            else:
                final_url = self._build_url_main(latitude, longitude)
            _LOGGER.debug("Формируем URL: %s", final_url)
            
            # Выполняем запрос и обрабатываем XML-ответ
            async with aiohttp.ClientSession() as session:
                async with session.get(final_url) as response:
                    if response.status != 200:
                        _LOGGER.error("Ошибка HTTP запроса: %s", response.status)
                        return None
                    text = await response.text()
                    root = ET.fromstring(text)
                    
                    if self._sensor_type == "index":
                        # Ищем блок stationFeatureCollection для сводного сенсора
                        if root.tag == "stationFeatureCollection":
                            additional_collection = root
                        else:
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
                            "pollen_index": additional_data.get("pollen_index"),
                            "responsible_elevated": additional_data.get("responsible_elevated")
                        }
                    elif self._sensor_type == "main":
                        # Ищем блок stationProfileFeatureCollection для сенсора "main"
                        main_collection = root.find(".//stationProfileFeatureCollection")
                        main_data = {}
                        if main_collection is not None:
                            station_features = main_collection.findall(".//stationFeature")
                            if station_features:
                                try:
                                    desired_altitude = float(self._altitude)
                                except (TypeError, ValueError):
                                    desired_altitude = None
                                best_feature = None
                                # Выбираем оптимальный stationFeature по близости к заданной высоте
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
                                    # Извлекаем pollen_value для выбранного типа пыльцы
                                    data_element = best_feature.find(".//data[@name='{}']".format(self._var))
                                    if data_element is not None:
                                        main_data["pollen_value"] = float(data_element.text)
                                        unit = data_element.get("units")
                                        if unit:
                                            main_data["unit_of_measurement"] = unit
                                    # Дополнительные атрибуты, такие как дата измерения и высота станции
                                    main_data["measurement_date"] = best_feature.get("date")
                                    main_data["measurement_altitude"] = best_feature.get("altitude")
                        return {"main": main_data}
        except Exception as e:
            _LOGGER.error("Ошибка при получении или обработке XML: %s", e)
            return None
