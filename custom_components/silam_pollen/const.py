# const.py
DOMAIN = "silam_pollen"
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_ALTITUDE = 275

# Базовые URL для запросов API SILAM
BASE_URL_V6_0 = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd"
)

BASE_URL_V5_9_1 = (
    "https://thredds.silam.fmi.fi/thredds/ncss/grid/silam_regional_pollen_v5_9_1/"
    "silam_regional_pollen_v5_9_1_best.ncd"
)

# Маппинг типов пыльцы: ключ – внутреннее название, значение – дефолтное (англ.) имя
VAR_OPTIONS = {
    "alder_m22": "alder",
    "birch_m22": "birch",
    "grass_m32": "grass",
    "hazel_m23": "hazel",
    "mugwort_m18": "mugwort",
    "olive_m28": "olive",
    "ragweed_m18": "ragweed"
}

URL_VAR_MAPPING = {
    "alder_m22": "cnc_POLLEN_ALDER_m22",
    "birch_m22": "cnc_POLLEN_BIRCH_m22",
    "grass_m32": "cnc_POLLEN_GRASS_m32",
    "hazel_m23": "cnc_POLLEN_HAZEL_m23",
    "mugwort_m18": "cnc_POLLEN_MUGWORT_m18",
    "olive_m28": "cnc_POLLEN_OLIVE_m28",
    "ragweed_m18": "cnc_POLLEN_RAGWEED_m18"
}

INDEX_MAPPING = {
    1: "very_low",
    2: "low",
    3: "moderate",
    4: "high",
    5: "very_high"
}
RESPONSIBLE_MAPPING = {
    -1: "missing",
    1: "alder",
    2: "birch",
    3: "grass",
    4: "olive",
    5: "mugwort",
    6: "ragweed",
    7: "hazel"
}