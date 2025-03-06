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
from .const import DOMAIN, VAR_OPTIONS

class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Конфигурационный мастер для интеграции SILAM Pollen с двумя шагами.
    
    Шаг 1: Пользователь выбирает базовые параметры – зону, высоту, типы пыльцы (опционально)
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
        default_altitude = getattr(self.hass.config, "elevation", 275)
        data_schema = vol.Schema({
            vol.Required("zone_id", default=default_zone): vol.In(zones),
            vol.Required("altitude", default=default_altitude): vol.Coerce(float),
            vol.Optional("var", default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "cnc_POLLEN_ALDER_m22",
                        "cnc_POLLEN_BIRCH_m22",
                        "cnc_POLLEN_GRASS_m32",
                        "cnc_POLLEN_HAZEL_m23",
                        "cnc_POLLEN_MUGWORT_m18",
                        "cnc_POLLEN_OLIVE_m28",
                        "cnc_POLLEN_RAGWEED_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config.pollen"
                )
            ),
            vol.Required("update_interval", default=5): vol.Coerce(int),
        })
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                description_placeholders={"altitude": "Altitude above sea level"}
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
            default_altitude = base_data.get("altitude", getattr(self.hass.config, "elevation", 275))

            schema_fields = collections.OrderedDict()
            schema_fields[vol.Optional("zone_name", default=default_zone_name)] = str
            schema_fields[vol.Required("location", default={
                "latitude": default_latitude,
                "longitude": default_longitude,
            })] = LocationSelector(LocationSelectorConfig(radius=False))
            schema_fields[vol.Required("altitude", default=default_altitude)] = vol.Coerce(float)

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
            altitude_input = getattr(self.hass.config, "elevation", 275)
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
                "update_interval",
                default=self.config_entry.options.get(
                    "update_interval", self.config_entry.data.get("update_interval", 5)
                )
            ): vol.Coerce(int),
            vol.Optional(
                "var",
                default=self.config_entry.options.get("var", self.config_entry.data.get("var", []))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "cnc_POLLEN_ALDER_m22",
                        "cnc_POLLEN_BIRCH_m22",
                        "cnc_POLLEN_GRASS_m32",
                        "cnc_POLLEN_HAZEL_m23",
                        "cnc_POLLEN_MUGWORT_m18",
                        "cnc_POLLEN_OLIVE_m28",
                        "cnc_POLLEN_RAGWEED_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config.pollen"
                )
            ),
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
