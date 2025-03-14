"""
sensor.py для интеграции SILAM Pollen в Home Assistant.

Реализует:
  - Динамическое формирование URL запроса к серверу SILAM на основе координат и выбранных аллергенов.
  - Централизованное обновление данных через SilamCoordinator (один запрос для всех сенсоров службы).
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
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from .const import DOMAIN, VAR_OPTIONS, INDEX_MAPPING, RESPONSIBLE_MAPPING, URL_VAR_MAPPING
from .coordinator import SilamCoordinator  # Импорт нового координатора

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настраивает интеграцию SILAM Pollen через config entry.

    Из настроек извлекаются:
      - base_device_name (entry.title) – уникальное имя службы.
      - Координаты и высота (altitude, manual_coordinates, latitude, longitude).
      - Список аллергенов (var).
      - Интервал обновления (update_interval).

    Создаётся экземпляр SilamCoordinator, которому передаются все параметры,
    после чего вызывается async_config_entry_first_refresh.
    Затем создаются:
      - Сводной сенсор "index" для общего индекса пыльцы.
      - Если список аллергенов не пуст, создаются индивидуальные сенсоры "main" для каждого аллергена.
    """
    base_device_name = entry.title

    altitude = entry.data.get("altitude")
    if altitude in (None, ""):
        altitude = hass.config.elevation
    manual_coordinates = entry.data.get("manual_coordinates", False)
    manual_latitude = entry.data.get("latitude")
    manual_longitude = entry.data.get("longitude")
    var_list = entry.options.get("var", entry.data.get("var", []))
    update_interval_minutes = entry.options.get("update_interval", entry.data.get("update_interval", 60))

    # Получаем уже созданный координатор из hass.data
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Координатор для записи %s не найден!", entry.entry_id)
        return

    sensors = []
    sensors.append(
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Index",
            base_device_name=base_device_name,
            coordinator=coordinator,
            var=var_list,  # Для index передаётся список аллергенов
            entry_id=entry.entry_id,
            sensor_type="index",
            desired_altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
        )
    )
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
      - "index": сводной сенсор, отображающий общий индекс пыльцы.
      - "main": сенсор для конкретного аллергена, отображающий значение pollen_value.
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

        # Определяем, какой набор используется, на основе base_url из координатора
        base_url = self.coordinator._base_url
        if "silam_europe_pollen" in base_url:
            dataset = "europe"
        elif "silam_regional_pollen" in base_url:
            dataset = "regional"
        else:
            dataset = "unknown"
            
        # Получаем версию SILAM из координатора
        sw_version = self.coordinator.silam_version.replace("_", ".")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_device_name,
            manufacturer=coordinates,
            model=self._base_device_name,
            model_id=dataset,
            sw_version=sw_version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://silam.fmi.fi/pollen.html?region={dataset}"
        )

        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

        if self._sensor_type == "index":
            self._attr_translation_key = "index"
            self._attr_has_entity_name = True
        elif self._sensor_type == "main":
            self._attr_translation_key = VAR_OPTIONS.get(self._var, self._var)
            self._attr_has_entity_name = True
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
        """
        data = self.coordinator.data
        if data is None:
            _LOGGER.error("Нет данных от координатора")
            return

        if self._sensor_type == "index":
            index_data = data.get("index")
            if index_data is None:
                _LOGGER.error("Нет данных для index")
                return
            additional_feature = index_data.find(".//stationFeature")
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
            main_data_xml = data.get("main")
            main_data = {}
            state_value = None
            if main_data_xml is not None:
                station_features = main_data_xml.findall(".//stationFeature")
                if station_features:
                    # Теперь выбираем первый элемент, так как API уже возвращает данные с указанной высотой
                    best_feature = station_features[0]
                    full_var = URL_VAR_MAPPING.get(self._var, self._var)
                    data_element = best_feature.find(f".//data[@name='{full_var}']")
                    if data_element is not None:
                        try:
                            pollen_val = float(data_element.text)
                            state_value = int(round(pollen_val))
                        except (ValueError, TypeError):
                            state_value = None
                        unit = data_element.get("units")
                        if unit:
                            main_data["unit_of_measurement"] = unit
                        station_elem = best_feature.find(".//station")
                        if station_elem is not None:
                            main_data["altitude"] = station_elem.get("altitude")
            self._state = state_value
            self._extra_attributes.update(main_data)