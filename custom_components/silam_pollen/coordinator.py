"""
coordinator.py

Реализует SilamCoordinator для интеграции SILAM Pollen.
Использует DataUpdateCoordinator для обновления данных для всех сенсоров интеграции.
"""

import logging
import re
import aiohttp
import async_timeout
import xml.etree.ElementTree as ET
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import URL_VAR_MAPPING, BASE_URL_V6_0  # Импортируем маппинг для преобразования переменных

_LOGGER = logging.getLogger(__name__)

class SilamCoordinator(DataUpdateCoordinator):
    """Координатор для интеграции SILAM Pollen."""

    def __init__(self, hass, base_device_name, var_list, manual_coordinates, manual_latitude, manual_longitude, desired_altitude, update_interval, base_url, forecast=False):
        """
        Инициализирует координатор.

        :param hass: экземпляр Home Assistant.
        :param base_device_name: имя службы, используемое для формирования имени координатора.
        :param var_list: список переменных (аллергенов), выбранных пользователем.
        :param manual_coordinates: булево значение, использовать ли ручные координаты.
        :param manual_latitude: ручная широта.
        :param manual_longitude: ручная долгота.
        :param desired_altitude: высота над уровнем моря, заданная пользователем.
        :param update_interval: интервал обновления (в минутах).
        :param base_url: базовый URL для запросов.
        :param forecast: включает режим прогноза (определяет длительность запроса).
        """
        self._base_device_name = base_device_name
        self._var_list = var_list
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._desired_altitude = desired_altitude
        self._base_url = base_url
        self._forecast_enabled = forecast
        # Извлекаем версию SILAM из BASE_URL
        match = re.search(r"pollen_v(\d+_\d+)", self._base_url)
        if match:
            self.silam_version = match.group(1)
        else:
            self.silam_version = "unknown"

        # Инициализируем merged_data (будет заполняться после обновления)
        self.merged_data = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"SILAM Pollen Coordinator ({base_device_name})",
            update_interval=timedelta(minutes=update_interval),
            always_update=True,
        )

    async def async_request_refresh(self, context=None):
        """
        Переопределённый метод принудительного обновления.
        Логирует контекст вызова (например, идентификатор сущности, которая запросила обновление).
        """
        _LOGGER.debug("Запрошено обновление данных. Контекст: %s", context)
        return await super().async_request_refresh()

    def _build_index_url(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсора index.
        Параметры:
          var=POLI
          var=POLISRC
          var=temp_2m
          latitude, longitude
          time_start=present
          time_duration=<значение из параметра self._forecast_enabled>
          accept=xml
        """
        time_duration = "PT36H" if self._forecast_enabled else "PT0H"
        query_params = [
            "var=POLI",
            "var=POLISRC",
            "var=temp_2m",
            f"latitude={latitude}",
            f"longitude={longitude}",
            "time_start=present",
            f"time_duration={time_duration}",
            "accept=xml"
        ]
        url = self._base_url + "?" + "&".join(query_params)
        return url

    def _build_main_url(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсоров main.
        Для каждого выбранного аллергена добавляется параметр var с преобразованием через URL_VAR_MAPPING.
        Плюс общие параметры:
          latitude, longitude
          time_start=present
          time_duration=<значение из параметра self._forecast_enabled>
          vertCoord=<desired_altitude>
          accept=xml
        """
        # Определяем длительность прогноза
        time_duration = "PT36H" if self._forecast_enabled else "PT0H"
    
        query_params = []
        if self._var_list:
            for allergen in self._var_list:
                full_allergen = URL_VAR_MAPPING.get(allergen, allergen)
                query_params.append(f"var={full_allergen}")
        query_params.append(f"latitude={latitude}")
        query_params.append(f"longitude={longitude}")
        query_params.append("time_start=present")
        query_params.append(f"time_duration={time_duration}")  # Добавляем параметр времени прогноза
        query_params.append(f"vertCoord={self._desired_altitude}")
        query_params.append("accept=xml")
        
        url = self._base_url + "?" + "&".join(query_params)
        return url

    async def _async_update_data(self):
        """
        Асинхронно обновляет данные через два HTTP-запроса:
          - Для сенсора index с использованием _build_index_url.
          - Для сенсоров main с использованием _build_main_url (если var_list не пуст).
        Возвращает словарь с ключами 'index' и 'main' (если применимо).
        """
        # Определяем координаты: если используются ручные координаты, то берем их,
        # иначе извлекаем координаты из зоны 'home'.
        if self._manual_coordinates and self._manual_latitude is not None and self._manual_longitude is not None:
            latitude = self._manual_latitude
            longitude = self._manual_longitude
        else:
            zone = self.hass.states.get("zone.home")
            if zone is None:
                raise UpdateFailed("Зона 'home' не найдена")
            latitude = zone.attributes.get("latitude")
            longitude = zone.attributes.get("longitude")

        index_url = self._build_index_url(latitude, longitude)
        _LOGGER.debug("Вызов API для index: %s", index_url)

        data = {}

        try:
            async with aiohttp.ClientSession() as session:
                # Запрос для index
                async with session.get(index_url) as response:
                    _LOGGER.debug("Ответ для index с кодом %s", response.status)
                    if response.status != 200:
                        raise UpdateFailed(f"HTTP error (index): {response.status}")
                    async with async_timeout.timeout(10):
                        text = await response.text()
                        _LOGGER.debug("Получен ответ для index: %s", text[:200])
                        data["index"] = ET.fromstring(text)

                # Если var_list задан, выполняем запрос для main
                if self._var_list:
                    main_url = self._build_main_url(latitude, longitude)
                    _LOGGER.debug("Вызов API для main: %s", main_url)
                    async with session.get(main_url) as response:
                        _LOGGER.debug("Ответ для main с кодом %s", response.status)
                        if response.status != 200:
                            raise UpdateFailed(f"HTTP error (main): {response.status}")
                        async with async_timeout.timeout(10):
                            text = await response.text()
                            _LOGGER.debug("Получен ответ для main: %s", text[:200])
                            data["main"] = ET.fromstring(text)
        except Exception as err:
            raise UpdateFailed(f"Ошибка при получении или обработке XML: {err}")

        # Объединяем данные один раз и кешируем в merged_data,
        # при этом оригинальный словарь data возвращается как есть для совместимости
        try:
            from .data_processing import merge_station_features
            merged = merge_station_features(
                data.get("index"),
                data.get("main"),
                forecast_enabled=self._forecast_enabled,
                selected_allergens=self._var_list
            )
            _LOGGER.debug("Сформированные объединённые данные: %s", merged)
            self.merged_data = {**merged}
        except Exception as err:
            _LOGGER.error("Ошибка при объединении или обработке прогнозных данных: %s", err)
            self.merged_data = {}