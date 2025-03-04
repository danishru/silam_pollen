import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

DOMAIN = "silam_pollen"

# Шаблон URL по умолчанию
DEFAULT_URL_TEMPLATE = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd?var={var}&latitude={latitude}&longitude={longitude}"
    "&time={time}&vertCoord={vertCoord}&accept=xml"
)

# Список вариантов для параметра var
VAR_OPTIONS = {
    "cnc_POLLEN_ALDER_m22": "Ольха",
    "cnc_POLLEN_BIRCH_m22": "Берёза",
    "cnc_POLLEN_GRASS_m32": "Травы",
    "cnc_POLLEN_HAZEL_m23": "Лещина",
    "cnc_POLLEN_MUGWORT_m18": "Полынь",
    "cnc_POLLEN_OLIVE_m28": "Олива",
    "cnc_POLLEN_RAGWEED_m18": "Амброзия"
}

class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Обработка настроек интеграции SILAM Pollen через UI."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input.get(CONF_NAME), data=user_input)
        
        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default="SILAM Pollen"): str,
            vol.Required("data_url", default=DEFAULT_URL_TEMPLATE): str,
            # Чекбокс для ручного задания координат
            vol.Required("manual_coordinates", default=False): bool,
            # Опциональные поля для ручного ввода координат
            vol.Optional("latitude"): vol.Coerce(float),
            vol.Optional("longitude"): vol.Coerce(float),
            # Значение высоты (vertCoord) с дефолтным значением 275
            vol.Required("altitude", default=275): vol.Coerce(float),
            # Выбор переменной из списка
            vol.Required("var", default="cnc_POLLEN_BIRCH_m22"): vol.In(VAR_OPTIONS),
            # Интервал опроса в минутах (по умолчанию 5)
            vol.Required("update_interval", default=5): vol.Coerce(int),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema)
