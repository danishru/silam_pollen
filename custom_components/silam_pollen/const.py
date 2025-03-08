# const.py
DOMAIN = "silam_pollen"
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_ALTITUDE = 275

# Маппинг типов пыльцы: ключ – внутреннее название, значение – дефолтное (англ.) имя
VAR_OPTIONS = {
    "cnc_POLLEN_ALDER_m22": "alder",
    "cnc_POLLEN_BIRCH_m22": "birch",
    "cnc_POLLEN_GRASS_m32": "grass",
    "cnc_POLLEN_HAZEL_m23": "hazel",
    "cnc_POLLEN_MUGWORT_m18": "mugwort",
    "cnc_POLLEN_OLIVE_m28": "olive",
    "cnc_POLLEN_RAGWEED_m18": "ragweed"
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