import collections
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DEFAULT_ALTITUDE

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
                    translation_key="config.pollen"
                )
            ),
            vol.Required("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=30)),
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
                "radius" : 5000,
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
        return self.async_create_entry(title=base_data["title"], data=base_data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Возвращает обработчик Options Flow для этой записи."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Обработчик Options Flow для интеграции SILAM Pollen."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Первый и единственный шаг Options Flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
                    translation_key="config.pollen"
                )
            ),
            vol.Optional(
                "update_interval",
                default=self.config_entry.options.get(
                    "update_interval", self.config_entry.data.get("update_interval", DEFAULT_UPDATE_INTERVAL)
                )
            ): vol.All(vol.Coerce(int), vol.Range(min=30)),
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
