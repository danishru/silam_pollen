"""
sensor.py для интеграции SILAM Pollen в Home Assistant.

Реализует:
  - Централизованное обновление данных через SilamCoordinator, который объединяет данные из двух
    источников (index и main) один раз за цикл обновления и сохраняет их в атрибуте merged_data.
  - Использование объединённых (кэшированных) данных для обновления состояний сенсоров.
  
Создаются два типа сенсоров:
  • "index" – сводной сенсор, отображающий общий индекс пыльцы. Он извлекает данные из объединённого
    словаря (merged_data) по ключу "now" для параметров "POLI" и "POLISRC" и определяет состояние через INDEX_MAPPING.
  • "main" – сенсоры для конкретных аллергенов. Для них используется объединённый словарь, из которого
    извлекается значение, соответствующее полному имени параметра (через URL_VAR_MAPPING).
"""

import logging
import re
from datetime import timedelta
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from .const import DOMAIN, VAR_OPTIONS, INDEX_MAPPING, RESPONSIBLE_MAPPING, URL_VAR_MAPPING
from .coordinator import SilamCoordinator  # Импорт координатора интеграции

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Настраивает интеграцию SILAM Pollen через config entry.

    Из настроек извлекаются:
      - base_device_name (entry.title) – уникальное имя службы.
      - Координаты и высота (altitude, manual_coordinates, latitude, longitude).
      - Список аллергенов (var).
      - Интервал обновления (update_interval).
    
    После создания координатора создаются:
      - Сенсор "index" – сводной сенсор, отображающий общий индекс пыльцы.
      - При наличии выбранных аллергенов создаются дополнительные сенсоры "main".
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

    # Получаем координатор, ранее сохранённый в hass.data
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Координатор для записи %s не найден!", entry.entry_id)
        return

    sensors = []
    # Создаём сенсор типа "index"
    sensors.append(
        SilamPollenSensor(
            sensor_name=f"{base_device_name} Index",
            base_device_name=base_device_name,
            coordinator=coordinator,
            var=var_list,  # Для index передаётся список аллергенов (используется для формирования имени)
            entry_id=entry.entry_id,
            sensor_type="index",
            desired_altitude=altitude,
            manual_coordinates=manual_coordinates,
            manual_latitude=manual_latitude,
            manual_longitude=manual_longitude,
        )
    )
    # Если выбраны конкретные аллергены, создаём сенсоры типа "main" для каждого из них
    if var_list:
        for pollen in var_list:
            translation_key = VAR_OPTIONS.get(pollen, pollen)
            sensors.append(
                SilamPollenSensor(
                    sensor_name=f"{base_device_name} {translation_key}",
                    base_device_name=base_device_name,
                    coordinator=coordinator,
                    var=pollen,  # Для main передаётся конкретный аллерген
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
    
    Различают два типа сенсоров:
      - "index": отображает общий индекс пыльцы, используя данные из ключа "now" объединённого словаря.
      - "main": отображает значение для конкретного аллергена, используя данные из ключа "now".
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

        # Формируем строку с GPS-координатами для DeviceInfo
        try:
            lat = round(float(self._manual_latitude), 3)
            lon = round(float(self._manual_longitude), 3)
            lat_hemisphere = "N" if lat >= 0 else "S"
            lon_hemisphere = "E" if lon >= 0 else "W"
            coordinates = f"GPS - {abs(lat):.3f}°{lat_hemisphere}, {abs(lon):.3f}°{lon_hemisphere}"
        except (ValueError, TypeError):
            coordinates = f"GPS - {self._manual_latitude}, {self._manual_longitude}"

        # Определяем используемый набор данных по base_url
        base_url = self.coordinator._base_url
        if "silam_europe_pollen" in base_url:
            dataset = "Europe v6.0"
        elif "silam_regional_pollen" in base_url:
            dataset = "Regional v5.9.1"
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

        # Регистрируем слушатель обновлений для автоматического обновления состояния сенсора
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

        # Настраиваем перевод и имя сущности в зависимости от типа сенсора
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
        Обновляет состояние сенсора, используя данные из объединённого словаря, сохранённого в self.coordinator.merged_data.

        Для сенсора "index":
          - Из раздела "now" объединённого словаря извлекается значение "POLI" и "POLISRC".
          - Состояние определяется через INDEX_MAPPING, а дополнительные атрибуты сохраняются.
        
        Для сенсора "main":
          - Из раздела "now" извлекается элемент с именем параметра (определяемым через URL_VAR_MAPPING).
          - Значение преобразуется в число, а единицы измерения и другие атрибуты сохраняются.
          - Если включён прогноз, добавляется атрибут "tomorrow", в котором хранится агрегированное значение прогноза пыльцы для завтрашнего дня.
        """
        merged = self.coordinator.merged_data
        if not merged or "now" not in merged:
            _LOGGER.error("Объединённые данные отсутствуют или не содержат ключ 'now'")
            return

        # Используем раздел "now" для получения данных
        entry = merged["now"]

        if self._sensor_type == "index":
            self._extra_attributes["date"] = entry.get("date")
            poli_raw = entry["data"].get("POLI", {}).get("value")
            try:
                index_value = int(float(poli_raw))
            except (ValueError, TypeError):
                index_value = None
            self._state = INDEX_MAPPING.get(index_value, "unknown")

            polisrc_raw = entry["data"].get("POLISRC", {}).get("value")
            try:
                re_value = int(float(polisrc_raw))
            except (ValueError, TypeError):
                re_value = None
            self._extra_attributes["responsible_elevated"] = RESPONSIBLE_MAPPING.get(re_value, "unknown")
            # Добавляем новый атрибут "index_tomorrow" только если включён прогноз
            if self.coordinator._forecast_enabled:
                twice_daily = merged.get("twice_daily_forecast", [])
                condition_tomorrow = None
                if twice_daily:
                    # Если первый прогноз дневной, берем третий (если он есть и тоже дневной)
                    if twice_daily[0].get("is_daytime"):
                        if len(twice_daily) >= 3 and twice_daily[2].get("is_daytime"):
                            condition_tomorrow = twice_daily[2].get("condition")
                    # Если первый прогноз ночной, то берем второй (если он дневной)
                    else:
                        if len(twice_daily) >= 2 and twice_daily[1].get("is_daytime"):
                            condition_tomorrow = twice_daily[1].get("condition")
                if condition_tomorrow is not None:
                    self._extra_attributes["index_tomorrow"] = condition_tomorrow

        elif self._sensor_type == "main":
            full_var = URL_VAR_MAPPING.get(self._var, self._var)
            data_element = entry["data"].get(full_var)
            state_value = None
            main_data = {}
            if data_element:
                try:
                    pollen_val = float(data_element.get("value"))
                    state_value = int(round(pollen_val))
                except (ValueError, TypeError):
                    state_value = None
                unit = data_element.get("units")
                if unit:
                    main_data["unit_of_measurement"] = unit

            station = entry.get("station", {})
            if station:
                main_data["altitude"] = station.get("altitude")

            self._state = state_value
            self._extra_attributes.update(main_data)
            # Добавляем атрибут "tomorrow" для сенсора main,
            # который содержит прогнозное значение пыльцы (агрегированное по forecast_key)
            if self.coordinator._forecast_enabled:
                twice_daily = merged.get("twice_daily_forecast", [])
                tomorrow_value = None
                # Ключ для аллергена формируется по схеме "pollen_<имя>", где имя определяется
                # как часть переменной до символа "_", приведённая к нижнему регистру.
                forecast_key = "pollen_" + self._var.split('_')[0].lower()
                if twice_daily:
                    if twice_daily[0].get("is_daytime"):
                        if len(twice_daily) >= 3 and twice_daily[2].get("is_daytime"):
                            tomorrow_value = twice_daily[2].get(forecast_key)
                    else:
                        if len(twice_daily) >= 2 and twice_daily[1].get("is_daytime"):
                            tomorrow_value = twice_daily[1].get(forecast_key)
                if tomorrow_value is not None:
                    self._extra_attributes["tomorrow"] = tomorrow_value
