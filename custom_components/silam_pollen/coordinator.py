"""
coordinator.py

Реализует SilamCoordinator для интеграции SILAM Pollen.
Использует DataUpdateCoordinator для одного запроса, обновляющего данные для всех сущностей интеграции.
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

    def __init__(self, hass, base_device_name, var_list, manual_coordinates, manual_latitude, manual_longitude, update_interval, base_url):
        """
        Инициализирует координатор.

        :param hass: экземпляр Home Assistant.
        :param base_device_name: имя службы, используемое для формирования имени координатора.
        :param var_list: список переменных (аллергенов), выбранных пользователем.
        :param manual_coordinates: булево значение, использовать ли ручные координаты.
        :param manual_latitude: ручная широта.
        :param manual_longitude: ручная долгота.
        :param update_interval: интервал обновления (в минутах).
        """
        self._base_device_name = base_device_name
        self._var_list = var_list
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._base_url = base_url
        # Извлекаем версию SILAM из BASE_URL
        match = re.search(r"pollen_v(\d+_\d+)", self._base_url)
        if match:
            self.silam_version = match.group(1)
        else:
            self.silam_version = "unknown"

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
        return await super().async_request_refresh(context=context)

    def _build_unified_url(self, latitude, longitude):
        """
        Формирует единый URL для запроса данных на основе координат и списка аллергенов.
        Если список var_list пуст, запрос содержит только обязательные параметры.
        """
        query_params = []
        if self._var_list:
            for allergen in self._var_list:
                # Преобразуем значение, например "alder_m22" в "cnc_POLLEN_ALDER_m22"
                full_allergen = URL_VAR_MAPPING.get(allergen, allergen)
                query_params.append(f"var={full_allergen}")
        query_params.append("var=POLI")
        query_params.append("var=POLISRC")
        query_params.append(f"latitude={latitude}")
        query_params.append(f"longitude={longitude}")
        query_params.append("time=present")
        query_params.append("accept=xml")
        url = self._base_url + "?" + "&".join(query_params)
        return url

    async def _async_update_data(self):
        """
        Асинхронно обновляет данные через HTTP-запрос и возвращает разобранный XML.
        Добавлен debug лог для каждого вызова API.
        """
        if self._manual_coordinates and self._manual_latitude is not None and self._manual_longitude is not None:
            latitude = self._manual_latitude
            longitude = self._manual_longitude
        else:
            zone = self.hass.states.get("zone.home")
            if zone is None:
                raise UpdateFailed("Зона 'home' не найдена")
            latitude = zone.attributes.get("latitude")
            longitude = zone.attributes.get("longitude")

        url = self._build_unified_url(latitude, longitude)
        _LOGGER.debug("Вызов API: отправляется запрос по URL: %s", url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    _LOGGER.debug("Получен ответ с кодом %s", response.status)
                    if response.status != 200:
                        raise UpdateFailed(f"HTTP error: {response.status}")
                    async with async_timeout.timeout(10):
                        text = await response.text()
                        _LOGGER.debug("Получен ответ: %s", text[:200])  # Логируем первые 200 символов
                        root = ET.fromstring(text)
                        return root
        except Exception as err:
            raise UpdateFailed(f"Ошибка при получении или обработке XML: {err}")
