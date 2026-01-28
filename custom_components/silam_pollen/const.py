# const.py
DOMAIN = "silam_pollen"
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_ALTITUDE = 275

# Базовые URL для запросов API SILAM (THREDDS NCSS grid)
THREDDS_NCSS_GRID_BASE = "https://thredds.silam.fmi.fi/thredds/ncss/grid"

# Europe pollen (new default)
BASE_URL_EUROPE_V6_1 = (
    f"{THREDDS_NCSS_GRID_BASE}/silam_europe_pollen_v6_1/"
    "silam_europe_pollen_v6_1_best.ncd"
)

# Europe pollen (legacy)
BASE_URL_EUROPE_V6_0 = (
    f"{THREDDS_NCSS_GRID_BASE}/silam_europe_pollen_v6_0/"
    "silam_europe_pollen_v6_0_best.ncd"
)

# Regional pollen
BASE_URL_REGIONAL_V5_9_1 = (
    f"{THREDDS_NCSS_GRID_BASE}/silam_regional_pollen_v5_9_1/"
    "silam_regional_pollen_v5_9_1_best.ncd"
)

# HIRES pollen (future, not enabled in UI yet)
BASE_URL_HIRES_V6_1 = (
    f"{THREDDS_NCSS_GRID_BASE}/silam_hires_pollen_v6_1/"
    "silam_hires_pollen_v6_1_best.ncd"
)


# Короткие ключи источников для SMART-склейки (raw_merged[*]["s"] и merged["src"])
# Значения задаём явно, чтобы ключи были стабильными и без вычислений.
DATASET_SRC_KEYS = {
    "silam_europe_pollen_v6_1": "sep61",
    "silam_europe_pollen_v6_0": "sep60",
    "silam_regional_pollen_v5_9_1": "srp591",
    "silam_hires_pollen_v6_1": "shp61",
}

# --- Backward-compatible aliases (keep for now) ---
BASE_URL_V6_0 = BASE_URL_EUROPE_V6_0
BASE_URL_V5_9_1 = BASE_URL_REGIONAL_V5_9_1

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

def resolve_silam_var_name(allergen: str, base_url: str | None = None) -> str:
    """
    Возвращает реальное имя переменной в SILAM/NCSS для выбранного датасета.

    На данном этапе:
    - UI/опции: остаётся 'olive_m28'
    - Для v6.1 (Europe/Hires): фактическая переменная = cnc_POLLEN_OLIVE_m20
    """
    if allergen == "olive_m28" and base_url:
        if "silam_europe_pollen_v6_1" in base_url or "silam_hires_pollen_v6_1" in base_url:
            return "cnc_POLLEN_OLIVE_m20"

    return URL_VAR_MAPPING.get(allergen, allergen)

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