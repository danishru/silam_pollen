import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "silam_pollen"

# Список вариантов для параметра var.
# Ключ – значение, используемое в запросе; значение – удобочитаемое название на английском.
VAR_OPTIONS = {
    "cnc_POLLEN_ALDER_m22": "Alder",
    "cnc_POLLEN_BIRCH_m22": "Birch",
    "cnc_POLLEN_GRASS_m32": "Grass",
    "cnc_POLLEN_HAZEL_m23": "Hazel",
    "cnc_POLLEN_MUGWORT_m18": "Mugwort",
    "cnc_POLLEN_OLIVE_m28": "Olive",
    "cnc_POLLEN_RAGWEED_m18": "Ragweed"
}

# Поле data_url не показывается пользователю, URL формируется в sensor.py.
DEFAULT_URL_TEMPLATE = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd?var={var}&latitude={latitude}&longitude={longitude}"
    "&time=present&accept=xml"
)

class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Конфигурационный мастер для интеграции SILAM Pollen.

    Настройка разделена на два шага:
      1. Первый шаг – базовые параметры: выбор переменной (var) и интервал опроса.
         Здесь значение altitude не запрашивается, оно подставляется автоматически из hass.config.elevation.
      2. Второй шаг – ручной ввод координат и возможность изменить altitude вручную.
         Значения по умолчанию для latitude и longitude берутся из состояния zone.home,
         а для altitude – из hass.config.elevation (или из данных первого шага).
    """
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Первый шаг конфигурации.

        Запрашиваются:
          - manual_coordinates: флаг для ручного ввода координат.
          - altitude: желаемая высота (подставляется автоматически и не редактируется на этом шаге).
          - var: выбор переменной из VAR_OPTIONS.
          - update_interval: интервал опроса в минутах.
        """
        if user_input is None:
            default_altitude = getattr(self.hass.config, "elevation", 275)
            data_schema = vol.Schema({
                vol.Required("manual_coordinates", default=False): bool,
                vol.Required("altitude", default=default_altitude): vol.Coerce(float),
                vol.Required("var", default="cnc_POLLEN_BIRCH_m22"): vol.In(VAR_OPTIONS),
                vol.Required("update_interval", default=5): vol.Coerce(int),
            })
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema
            )
        
        # Сохраняем данные первого шага и переходим ко второму шагу для ввода координат.
        self._base_data = user_input.copy()
        return await self.async_step_manual_coords(None)

    async def async_step_manual_coords(self, user_input):
        """
        Второй шаг конфигурации для ручного ввода координат и возможности переопределения altitude.

        Запрашиваются:
          - latitude: широта.
          - longitude: долгота.
          - altitude: высота (пользователь может изменить значение).
        """
        if user_input is None:
            default_latitude = "unknown"
            default_longitude = "unknown"
            zone = self.hass.states.get("zone.home")
            if zone is not None:
                default_latitude = zone.attributes.get("latitude", "unknown")
                default_longitude = zone.attributes.get("longitude", "unknown")
            default_altitude = getattr(self.hass.config, "elevation", self._base_data.get("altitude", 275))
            data_schema = vol.Schema({
                vol.Required("latitude", default=default_latitude): vol.Coerce(float),
                vol.Required("longitude", default=default_longitude): vol.Coerce(float),
                vol.Required("altitude", default=default_altitude): vol.Coerce(float),
            })
            # Пример описания для пользователя (без параметра description, чтобы избежать ошибок)
            return self.async_show_form(
                step_id="manual_coords",
                data_schema=data_schema
            )
        
        # Объединяем данные первого и второго шагов.
        base_data = self._base_data.copy()
        base_data.update(user_input)
        # Формируем имя интеграции автоматически на основании выбранного var.
        chosen_var = base_data.get("var")
        display_name = VAR_OPTIONS.get(chosen_var, "")
        base_data["title"] = f"SILAM Pollen {display_name}"
        return self.async_create_entry(title=base_data["title"], data=base_data)
