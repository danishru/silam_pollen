import collections
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

DOMAIN = "silam_pollen"

VAR_OPTIONS = {
    "cnc_POLLEN_ALDER_m22": "Alder",
    "cnc_POLLEN_BIRCH_m22": "Birch",
    "cnc_POLLEN_GRASS_m32": "Grass",
    "cnc_POLLEN_HAZEL_m23": "Hazel",
    "cnc_POLLEN_MUGWORT_m18": "Mugwort",
    "cnc_POLLEN_OLIVE_m28": "Olive",
    "cnc_POLLEN_RAGWEED_m18": "Ragweed"
}

class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Конфигурационный мастер для интеграции SILAM Pollen с двумя шагами.

    Шаг 1: Пользователь выбирает базовые параметры – зону (из динамического списка),
            altitude, var и update_interval.
    Шаг 2: Отображаются координаты, полученные из выбранной зоны, и предлагается ввести (или исправить)
            zone_name, а также выбрать координаты через селектор местоположения (карта).
            Итоговое имя интеграции будет формироваться как "SILAM Pollen - <zone_name>".
    """
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Шаг 1: базовые параметры (без координат)."""
        zones = {
            state.entity_id: state.attributes.get("friendly_name", state.entity_id)
            for state in self.hass.states.async_all() if state.entity_id.startswith("zone.")
        }
        if not zones:
            zones = {"zone.home": "Home"}
        default_zone = "zone.home" if "zone.home" in zones else list(zones.keys())[0]
        default_altitude = getattr(self.hass.config, "elevation", 275)
        data_schema = vol.Schema({
            vol.Required("zone_id", default=default_zone): vol.In(zones),
            vol.Required("altitude", default=default_altitude): vol.Coerce(float),
            vol.Required("var", default="cnc_POLLEN_BIRCH_m22"): vol.In(VAR_OPTIONS),
            vol.Required("update_interval", default=5): vol.Coerce(int),
        })
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        # Сохраняем данные первого шага в context
        self.context["base_data"] = user_input.copy()
        self.context["zone_id"] = user_input.get("zone_id")
        return await self.async_step_manual_coords()

    async def async_step_manual_coords(self, user_input=None):
        """Шаг 2: ввод координат и zone_name с использованием селектора местоположения."""
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
            # Поле zone_name – отображается первым (выше карты)
            schema_fields[vol.Optional("zone_name", default=default_zone_name)] = str
            # Далее селектор местоположения – он рендерит карту и ниже показывает поля для ввода координат
            schema_fields[vol.Required("location", default={
                "latitude": default_latitude,
                "longitude": default_longitude,
            })] = LocationSelector(LocationSelectorConfig(radius=False))
            # Поле altitude – внизу
            schema_fields[vol.Required("altitude", default=default_altitude)] = vol.Coerce(float)

            data_schema = vol.Schema(schema_fields)
            return self.async_show_form(step_id="manual_coords", data_schema=data_schema)

        # Обработка введённых данных
        location = user_input.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        base_data = self.context.get("base_data", {})
        base_data["latitude"] = latitude
        base_data["longitude"] = longitude
        base_data["altitude"] = user_input.get("altitude")
        base_data["zone_name"] = user_input.get("zone_name")
        base_data["title"] = f"SILAM Pollen - {base_data['zone_name']}"
        return self.async_create_entry(title=base_data["title"], data=base_data)
