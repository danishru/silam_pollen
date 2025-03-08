"""
sensor.py для интеграции SILAM Pollen в Home Assistant.

Реализует:
  - Динамическое формирование URL запроса к серверу SILAM на основе координат и выбранных аллергенов.
  - Централизованное обновление данных через DataUpdateCoordinator (один запрос для всех сенсоров службы).
  - Создание двух типов сенсоров:
      • "index" – сводной сенсор, отображающий общий индекс пыльцы.
      • "main" – сенсоры для конкретных аллергенов.
      
Особенность:
  Если пользователь не выбрал никаких аллергенов (var_list пуст),
  сервер вернет XML вида:
  
  <?xml version="1.0" encoding="UTF-8"?>
  <stationFeatureCollection>
      <stationFeature date="2025-03-05T21:00:00Z">
          <station name="GridPointRequestedAt[55.000N_37.000E]" latitude="54.965" longitude="36.973" altitude="0">
              GridPointRequestedAt[55.000N_37.000E]
          </station>
          <data name="POLI" units="">2</data>
          <data name="POLISRC" units="">1</data>
      </stationFeature>
  </stationFeatureCollection>
  
При этом для такой службы будет создаваться только сводной сенсор "index".
"""

import logging
import re
from datetime import timedelta
import aiohttp
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from .const import DOMAIN, VAR_OPTIONS, DEFAULT_UPDATE_INTERVAL, INDEX_MAPPING, RESPONSIBLE_MAPPING

_LOGGER = logging.getLogger(__name__)

# Базовый URL для запроса данных SILAM Pollen
BASE_URL = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd"
)

# Извлекаем версию SILAM из BASE_URL с помощью регулярного выражения
match = re.search(r"pollen_v(\d+_\d+)", BASE_URL)
if match:
    SILAM_VERSION = match.group(1)
else:
    SILAM_VERSION = "unknown"

def _build_unified_url(latitude, longitude, var_list):
    """
    Формирует единый URL для запроса к серверу SILAM на основе координат и списка аллергенов.

    Если список var_list пустой:
      URL содержит только обязательные параметры: POLI и POLISRC.
      (Пример: ...?var=POLI&var=POLISRC&latitude=55.9&longitude=37.5&time=present&accept=xml)
      
    Если список не пустой:
      URL включает выбранные аллергены, затем обязательные параметры.
      (Пример: ...?var=cnc_POLLEN_ALDER_m22&var=cnc_POLLEN_HAZEL_m23&var=cnc_POLLEN_GRASS_m32&
                var=POLI&var=POLISRC&latitude=55.0&longitude=37.0&time=present&accept=xml)
    """
    query_params = []
    if var_list:
        for allergen in var_list:
            query_params.append(f"var={allergen}")
    query_params.append("var=POLI")
    query_params.append("var=POLISRC")
    query_params.append(f"latitude={latitude}")
    query_params.append(f"longitude={longitude}")
    query_params.append("time=present")
    query_params.append("accept=xml")
    url = BASE_URL + "?" + "&".join(query_params)
    return url

async def async_update_data(hass, var_list, manual_coordinates, manual_latitude, manual_longitude):
    """
    Асинхронная функция для обновления данных.

    Определяет координаты:
      - Если включены ручные координаты, используются они.
      - Иначе берутся координаты из состояния 'zone.home'.
      
    Формируется URL через _build_unified_url и выполняется HTTP-запрос.
    Разбирается XML-ответ и возвращается его корневой элемент.
    При ошибке выбрасывается UpdateFailed.
    """
    if manual_coordinates and manual_latitude is not None and manual_longitude is not None:
        latitude = manual_latitude
        longitude = manual_longitude
    else:
        zone = hass.states.get("zone.home")
        if zone is None:
            raise UpdateFailed("Зона 'home' не найдена")
        latitude = zone.attributes.get("latitude")
        longitude = zone.attributes.get("longitude")
    
    url = _build_unified_url(latitude, longitude, var_list)
    _LOGGER.debug("Запуск update_method: выполняется запрос по URL: %s", url)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise UpdateFailed(f"HTTP error: {response.status}")
                text = await response.text()
                root = ET.fromstring(text)
                return root
    except Exception as err:
        raise UpdateFailed(f"Ошибка при получении или обработке XML: {err}")

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настраивает интеграцию SILAM Pollen через config entry.

    Из настроек извлекаются:
      - base_device_name (entry.title) – уникальное имя службы.
      - Координаты и высота (altitude, manual_coordinates, latitude, longitude).
      - Список аллергенов (var).
      - Интервал обновления (update_interval).

    Создается отдельный DataUpdateCoordinator для данной службы, который выполняет один HTTP‑запрос
    за интервал обновления. Затем создаются:
      - Сводной сенсор "index" для общего индекса пыльцы.
      - Если список аллергенов не пуст, создаются индивидуальные сенсоры "main" для каждого аллергена.
    """
    base_device_name = entry.title


    # Извлекаем высоту: если высота не указана (None или пустая строка), берём из конфигурации
    altitude = entry.data.get("altitude")
    if altitude in (None, ""):
        altitude = hass.config.elevation
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval_minutes = entry.options.get("update_interval", entry.data.get("update_interval", DEFAULT_UPDATE_INTERVAL))

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"SILAM Pollen Coordinator ({base_device_name})",
        update_method=lambda: async_update_data(hass, var_list, manual_coordinates, manual_latitude, manual_longitude),
        update_interval=timedelta(minutes=update_interval_minutes),
    )
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    # Создаем сводной сенсор "index"
    sensors.append(
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Index",
            base_device_name=base_device_name,
            coordinator=coordinator,
            var=var_list,  # Для index передается список аллергенов
            entry_id=entry.entry_id,
            sensor_type="index",
            desired_altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
        )
    )
    # Если аллергены выбраны, создаем сенсоры "main"
    if var_list:
        for pollen in var_list:
            translation_key = VAR_OPTIONS.get(pollen, pollen)
            sensors.append(
                SilamPollenSensor(
                    sensor_name=f"{base_device_name} {translation_key}",
                    base_device_name=base_device_name,
                    coordinator=coordinator,
                    var=pollen,  # Для main – конкретный аллерген
                    entry_id=entry.entry_id,
                    sensor_type="main",
                    desired_altitude=altitude,
                    manual_coordinates=manual_coordinates,
                    manual_latitude=manual_latitude,
                    manual_longitude=manual_longitude,
                )
            )

    async_add_entities(sensors, True)

class SilamPollenSensor(SensorEntity):
    """
    Класс сенсора SILAM Pollen.

    Сенсоры делятся на два типа:
      - "index": сводной сенсор, отображающий общий индекс пыльцы (из блока stationFeatureCollection).
                 Для него задается translation_key равный "index", has_entity_name = True и fallback‑имя.
      - "main": сенсор для конкретного аллергена, отображающий значение pollen_value
                (из блока stationProfileFeatureCollection, с выбором оптимальной станции по высоте).
                Для него translation_key берется из VAR_OPTIONS, has_entity_name = True и задается fallback‑имя.
                
    Для каждой службы используется уникальное имя (base_device_name из entry.title).
    Дополнительно передаются ручные координаты для формирования информации об устройстве.
    """
    def __init__(self, sensor_name, base_device_name, coordinator, var, entry_id, sensor_type, desired_altitude,
                 manual_coordinates, manual_latitude, manual_longitude):
        self._base_device_name = base_device_name
        self.coordinator = coordinator
        self._var = var
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        self._desired_altitude = desired_altitude
        self._state = None
        self._extra_attributes = {}
        self._unit_of_measurement = None

        # Сохраняем параметры для формирования информации об устройстве
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude

        # Формирование строки с GPS-координатами для отображения в DeviceInfo.
        try:
            lat = round(float(self._manual_latitude), 3)
            lon = round(float(self._manual_longitude), 3)
            lat_hemisphere = "N" if lat >= 0 else "S"
            lon_hemisphere = "E" if lon >= 0 else "W"
            coordinates = f"GPS - {abs(lat):.3f}°{lat_hemisphere}, {abs(lon):.3f}°{lon_hemisphere}"
        except (ValueError, TypeError):
            coordinates = f"GPS - {self._manual_latitude}, {self._manual_longitude}"

        sw_version = SILAM_VERSION.replace("_", ".")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_device_name,
            manufacturer=coordinates,
            model=self._base_device_name,
            sw_version=sw_version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://silam.fmi.fi/pollen.html?region=europe"
        )

        # Подписываемся на обновления координатора для автоматического обновления состояния
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

        # Настройка локализации
        if self._sensor_type == "index":
            self._attr_translation_key = "index"
            # Убираем установку has_entity_name, чтобы fallback‑имя не комбинировалось с именем устройства
            self._attr_has_entity_name = True
            #self._attr_name = "index"  # fallback‑имя (будет заменено переводом, если настроен)
        elif self._sensor_type == "main":
            self._attr_translation_key = VAR_OPTIONS.get(self._var, self._var)
            self._attr_has_entity_name = True
            # Устанавливаем fallback‑имя только как значение из VAR_OPTIONS (например, "alder")
            #self._attr_name = VAR_OPTIONS.get(self._var, self._var)
        else:
            self._attr_translation_key = None
            self._attr_has_entity_name = False
            self._attr_name = sensor_name

    @property
    def unique_id(self):
        if self._sensor_type == "index":
            return f"{self._entry_id}_index"
        return f"{self._entry_id}_main_{self._var}"
        
    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attributes

    @property
    def native_unit_of_measurement(self):
        if self._sensor_type == "main":
            return self._unit_of_measurement
        return None

    @property
    def suggested_display_precision(self):
        if self._sensor_type == "main":
            return 0
        return None

    async def async_update(self):
        """
        Обновляет состояние сенсора, используя данные, полученные координатором.

        Для сенсора "index":
          - Если корневой элемент равен stationFeatureCollection, используем его напрямую,
            иначе ищем его среди дочерних элементов.
          - Извлекаются значения POLI и POLISRC, которые преобразуются в текстовое описание.
          
        Для сенсора "main":
          - Извлекается блок stationProfileFeatureCollection,
          - Выбирается оптимальная станция по близости к desired_altitude,
          - Извлекается pollen_value и единицы измерения для конкретного аллергена.
        """
        data = self.coordinator.data
        if data is None:
            _LOGGER.error("Нет данных от координатора")
            return

        if self._sensor_type == "index":
            if data.tag == "stationFeatureCollection":
                additional_collection = data
            else:
                additional_collection = data.find(".//stationFeatureCollection")
            if additional_collection is not None:
                additional_feature = additional_collection.find(".//stationFeature")
                if additional_feature is not None:
                    date_val = additional_feature.get("date")
                    if date_val:
                        self._extra_attributes["date"] = date_val
                    poli_elem = additional_feature.find(".//data[@name='POLI']")
                    if poli_elem is not None:
                        try:
                            index_value = int(float(poli_elem.text))
                        except (ValueError, TypeError):
                            index_value = None
                        self._state = INDEX_MAPPING.get(index_value, "unknown")
                    else:
                        self._state = None
                    polisrc_elem = additional_feature.find(".//data[@name='POLISRC']")
                    if polisrc_elem is not None:
                        try:
                            re_value = int(float(polisrc_elem.text))
                        except (ValueError, TypeError):
                            re_value = None
                        self._extra_attributes["responsible_elevated"] = RESPONSIBLE_MAPPING.get(re_value, "unknown")
        elif self._sensor_type == "main":
            main_collection = data.find(".//stationProfileFeatureCollection")
            main_data = {}
            if main_collection is not None:
                station_features = main_collection.findall(".//stationFeature")
                if station_features:
                    best_feature = None
                    if self._desired_altitude is not None:
                        best_diff = None
                        for sf in station_features:
                            alt_attr = sf.get("altitude")
                            if alt_attr is None:
                                continue
                            try:
                                alt_value = float(alt_attr)
                            except ValueError:
                                continue
                            diff = abs(alt_value - self._desired_altitude)
                            if best_diff is None or diff < best_diff:
                                best_diff = diff
                                best_feature = sf
                    if best_feature is None:
                        best_feature = station_features[0]
                    
                    if best_feature is not None:
                        data_element = best_feature.find(f".//data[@name='{self._var}']")
                        if data_element is not None:
                            try:
                                pollen_val = float(data_element.text)
                                state_value = int(round(pollen_val))
                            except (ValueError, TypeError):
                                state_value = None
                            unit = data_element.get("units")
                            if unit:
                                main_data["unit_of_measurement"] = unit
                        main_data["altitude"] = best_feature.get("altitude")
            self._state = state_value
            # Теперь не добавляем "pollen_value" в main_data, чтобы избежать дублирования
            self._extra_attributes.update(main_data)