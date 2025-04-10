import collections
import voluptuous as vol
import aiohttp
import async_timeout
import xml.etree.ElementTree as ET
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_ALTITUDE,
    BASE_URL_V5_9_1,
    BASE_URL_V6_0,
)

_LOGGER = logging.getLogger(__name__)

class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Конфигурационный мастер для интеграции SILAM Pollen с двумя шагами.
    
    Шаг 1: Пользователь выбирает базовые параметры – зону наблюдения, типы пыльцы (опционально)
           и интервал обновления.
    Шаг 2: Отображаются координаты выбранной зоны и предлагается ввести (или исправить)
           название зоны и координаты через селектор местоположения.
           Итоговое имя интеграции формируется как "SILAM Pollen - {zone_name}".
    """
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Шаг 1: базовые параметры (без координат)."""
        zones = {
            state.entity_id: state.attributes.get("friendly_name", state.entity_id)
            for state in self.hass.states.async_all()
            if state.entity_id.startswith("zone.")
        }
        if not zones:
            zones = {"zone.home": "Home"}
        default_zone = "zone.home" if "zone.home" in zones else list(zones.keys())[0]
        default_altitude = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)
        # Создаем список опций из словаря zones
        zone_options = [{"value": zone_id, "label": name} for zone_id, name in zones.items()]
        data_schema = vol.Schema({
            vol.Required("zone_id", default=default_zone): SelectSelector(
                SelectSelectorConfig(
                    options=zone_options,
                    multiple=False,
                    mode="dropdown"
                )
            ),
            #vol.Required("altitude", default=default_altitude): vol.Coerce(float),
            vol.Optional("var", default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "alder_m22",
                        "birch_m22",
                        "grass_m32",
                        "hazel_m23",
                        "mugwort_m18",
                        "olive_m28",
                        "ragweed_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config_pollen"
                )
            ),
            vol.Required("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=30)),
            vol.Optional("forecast", default=False): bool,
        })
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema
            )

        # Сохраняем данные первого шага в context
        self.context["base_data"] = user_input.copy()
        self.context["zone_id"] = user_input.get("zone_id")
        return await self.async_step_manual_coords()

    async def async_step_manual_coords(self, user_input=None):
        """Шаг 2: ввод координат и названия зоны."""
        if user_input is None:
            zone_id = self.context.get("zone_id", "zone.home")
            zone = self.hass.states.get(zone_id)
            if zone is not None:
                default_latitude = zone.attributes.get("latitude", self.hass.config.latitude)
                default_longitude = zone.attributes.get("longitude", self.hass.config.longitude)
                default_zone_name = zone.attributes.get("friendly_name", "Home")
            else:
                default_latitude = self.hass.config.latitude
                default_longitude = self.hass.config.longitude
                default_zone_name = "Home"
            base_data = self.context.get("base_data", {})
            # Если выбрана зона "zone.home", берем высоту из hass.config.elevation,
            # иначе используем DEFAULT_ALTITUDE из const.py.
            if zone_id == "zone.home":
                default_altitude = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)
            else:
                default_altitude = DEFAULT_ALTITUDE

            schema_fields = collections.OrderedDict()
            schema_fields[vol.Optional("zone_name", default=default_zone_name)] = str
            schema_fields[vol.Required("altitude", default=default_altitude)] = vol.Coerce(float)
            schema_fields[vol.Required("location", default={
                "latitude": default_latitude,
                "longitude": default_longitude,
                "radius": 5000,
            })] = LocationSelector(LocationSelectorConfig(radius=True))

            data_schema = vol.Schema(schema_fields)
            return self.async_show_form(
                step_id="manual_coords",
                data_schema=data_schema,
                description_placeholders={"altitude": "Altitude above sea level"}
            )

        # Обработка введённых данных
        location = user_input.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        altitude_input = user_input.get("altitude")
        if altitude_input in (None, ""):
            altitude_input = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)
        base_data = self.context.get("base_data", {})
        base_data["latitude"] = latitude
        base_data["longitude"] = longitude
        base_data["altitude"] = altitude_input
        base_data["zone_name"] = user_input.get("zone_name")
        base_data["manual_coordinates"] = True
        base_data["title"] = "SILAM Pollen - {zone_name}".format(zone_name=base_data["zone_name"])
        # Сохранение параметра "forecast" из первого шага
        base_data["forecast"] = self.context.get("base_data", {}).get("forecast", False)
        # Добавляем уникальный идентификатор на основе координат.
        # (Можно использовать другую логику для генерации уникального идентификатора)
        unique_id = f"{latitude}_{longitude}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Выполняем тестовый запрос к API с использованием введённых координат.
        # Метод _test_api возвращает True, None и выбранный URL (chosen_url) при успешном ответе.
        valid, error, chosen_url = await self._test_api(latitude, longitude)
        if not valid:
            errors = {"base": error}
            return self.async_show_form(
                step_id="manual_coords",
                data_schema=vol.Schema({
                    vol.Optional("zone_name", default=base_data["zone_name"]): str,
                    vol.Required("altitude", default=altitude_input): vol.Coerce(float),
                    vol.Required("location", default={
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius": 5000,
                    }): LocationSelector(LocationSelectorConfig(radius=True)),
                }),
                errors=errors,
                description_placeholders={"altitude": "Altitude above sea level"}
            )
        # Сохраняем выбранный базовый URL в конфигурационных данных.
        base_data["base_url"] = chosen_url
        return self.async_create_entry(title=base_data["title"], data=base_data)

    async def _test_api(self, latitude, longitude):
        """
        Вспомогательный метод для проверки доступности API с использованием введённых координат.
        Сначала пытается запрос к BASE_URL_V5_9_1, если статус не равен 200 – обращается к BASE_URL_V6_0.
        Если один из базовых URL возвращает статус 200, метод возвращает True, None и выбранный URL.
        """
        urls = [BASE_URL_V5_9_1, BASE_URL_V6_0]
        last_response = ""
        chosen_url = None
        for url in urls:
            test_url = url + f"?var=POLI&latitude={latitude}&longitude={longitude}&time=present&accept=xml"
            try:
                async with aiohttp.ClientSession() as session:
                    async with async_timeout.timeout(10):
                        async with session.get(test_url) as response:
                            text = await response.text()
                            if response.status == 200:
                                chosen_url = url
                                return True, None, chosen_url
                            else:
                                last_response = text
                                _LOGGER.debug("API returned %s from %s: %s", response.status, url, text)
            except Exception as err:
                last_response = str(err)
                _LOGGER.debug("Exception when requesting %s: %s", url, str(err))
        return False, last_response, None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Возвращает обработчик Options Flow для этой записи."""
        # Возвращаем OptionsFlowHandler без передачи config_entry
        return OptionsFlowHandler()

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Обработчик Options Flow для интеграции SILAM Pollen."""

    async def async_step_init(self, user_input=None):
        """Первый и единственный шаг Options Flow."""
        if user_input is not None:
            
            # Если пользователь выбрал forecast_daily, то автоматически устанавливаем forecast_hourly в True
            if user_input.get("forecast_daily"):
                user_input["forecast_hourly"] = True
                
            # Обновляем опции
            new_options = dict(self.config_entry.options)
            new_options.update(user_input)
            
            # Обновляем данные: base_url хранится в data и используется координатором
            new_data = dict(self.config_entry.data)
            new_version = user_input.get("version")
            new_data["version"] = new_version
            if new_version == "v5_9_1":
                new_data["base_url"] = BASE_URL_V5_9_1
            elif new_version == "v6_0":
                new_data["base_url"] = BASE_URL_V6_0
            else:
                new_data["base_url"] = "unknown"
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data, options=new_options)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        # Если user_input is None – показываем форму с предустановленным значением версии.
        # Определяем значение автоматически по base_url из записи.
        base_url = self.config_entry.data.get("base_url", "")
        if "silam_europe_pollen" in base_url:
            default_version = "v6_0"
        elif "silam_regional_pollen" in base_url:
            default_version = "v5_9_1"
        else:
            default_version = "unknown"

        # Тестируем доступность BASE_URL_V5_9_1 с использованием координат из записи.
        lat = self.config_entry.data.get("latitude")
        lon = self.config_entry.data.get("longitude")
        device_name = self.config_entry.title  # Имя устройства
        v5_9_1_available = False
        if lat is not None and lon is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    async with async_timeout.timeout(10):
                        test_url = BASE_URL_V5_9_1 + f"?var=POLI&latitude={lat}&longitude={lon}&time=present&accept=xml"
                        async with session.get(test_url) as response:
                            if response.status == 200:
                                v5_9_1_available = True
                                _LOGGER.debug(
                                    "Successful check: URL %s is available for device %s",
                                    test_url, device_name
                                )
            except Exception as err:
                _LOGGER.debug(
                    "Test request for v5_9_1 failed for device %s on URL %s: %s",
                    device_name, test_url, err
                )

        # Если тест v5_9_1 не прошёл, вариант выбора будет только v6_0.
        if v5_9_1_available:
            version_options = [
                {"value": "v6_0", "label": "SILAM Europe (v6.0)"},
                {"value": "v5_9_1", "label": "SILAM Regional (v5.9.1)"}
            ]
        else:
            version_options = [
                {"value": "v6_0", "label": "SILAM Europe (v6.0)"}
            ]
            default_version = "v6_0"

        data_schema = vol.Schema({
            vol.Optional(
                "var",
                default=self.config_entry.options.get("var", self.config_entry.data.get("var", []))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "alder_m22",
                        "birch_m22",
                        "grass_m32",
                        "hazel_m23",
                        "mugwort_m18",
                        "olive_m28",
                        "ragweed_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config_pollen"
                )
            ),
            vol.Optional(
                "update_interval",
                default=self.config_entry.options.get("update_interval", self.config_entry.data.get("update_interval", DEFAULT_UPDATE_INTERVAL))
            ): vol.All(vol.Coerce(int), vol.Range(min=30)),
            vol.Optional(
                "version",
                default=self.config_entry.options.get("version", self.config_entry.data.get("version", default_version))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=version_options,
                    multiple=False,
                    mode="dropdown"
                )
            ),
            vol.Optional(
                "forecast",
                default=self.config_entry.options.get("forecast", self.config_entry.data.get("forecast", False))
            ): bool,
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
