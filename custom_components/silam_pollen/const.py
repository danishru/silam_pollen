# const.py
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "silam_pollen"

# hass.data[DOMAIN] key for shared runs catalog manager
RUNS_CATALOG_MANAGER = "runs_catalog_manager"

# THREDDS catalog namespace (для runs/catalog.xml)
THREDDS_CATALOG_NS = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"}

# TTL кэша runs/catalog.xml (по умолчанию 45 минут)
RUNS_CATALOG_TTL_SECONDS = 45 * 60

DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_ALTITUDE = 275

# Базовые URL для запросов API SILAM (THREDDS NCSS grid)
THREDDS_NCSS_GRID_BASE = "https://thredds.silam.fmi.fi/thredds/ncss/grid"


# ---------------------------------------------------------------------------
# DATASETS: единый справочник датасетов (источник правды)
# - src: короткий ключ источника (raw_merged[*]["s"] и merged["src"])
# - path/file: из них строим base_url
# - label: человекочитаемое имя (для UI)
# - probe_priority: порядок приоритета для SMART-проверки доступности по координатам
#                   (меньше = выше приоритет)
# - ui_enabled: показывать ли датасет в ручном выборе OptionsFlow
# - ui_requires_probe: показывать только если датасет доступен по координатам
# - ui_order: порядок в dropdown OptionsFlow (меньше = выше)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DatasetMeta:
    """Метаданные датасета SILAM/THREDDS."""
    src: str
    path: str
    file: str
    label: str | None = None

    # SMART/probe приоритет
    probe_priority: int | None = None

    # UI политика (OptionsFlow)
    ui_enabled: bool = True
    ui_requires_probe: bool = False
    ui_order: int | None = None


DATASETS: dict[str, DatasetMeta] = {
    # Europe pollen (v6.1) — новый основной датасет для Европы (дефолт)
    "silam_europe_pollen_v6_1": DatasetMeta(
        src="sep61",
        path="silam_europe_pollen_v6_1",
        file="silam_europe_pollen_v6_1_best.ncd",
        label="SILAM Europe (v6.1)",
        probe_priority=30,
        ui_enabled=True,
        ui_requires_probe=False,
        ui_order=30,
    ),

    # Europe pollen (v6.0) — устаревший датасет (legacy)
    "silam_europe_pollen_v6_0": DatasetMeta(
        src="sep60",
        path="silam_europe_pollen_v6_0",
        file="silam_europe_pollen_v6_0_best.ncd",
        label="SILAM Europe (v6.0, legacy)",
        probe_priority=40,
        ui_enabled=True,
        ui_requires_probe=False,
        ui_order=40,
    ),

    # Regional pollen (v5.9.1) — региональный датасет (Северная Европа)
    "silam_regional_pollen_v5_9_1": DatasetMeta(
        src="srp591",
        path="silam_regional_pollen_v5_9_1",
        file="silam_regional_pollen_v5_9_1_best.ncd",
        label="SILAM Northern Europe (v5.9.1)",
        probe_priority=20,
        ui_enabled=True,
        ui_requires_probe=True,   # показываем в UI только если доступен по координатам
        ui_order=20,
    ),

    # HIRES pollen (v6.1) — высокодетальный датасет (Finland / северные широты)
    # Уже используется в интеграции (доступен по покрытию координат).
    "silam_hires_pollen_v6_1": DatasetMeta(
        src="shp61",
        path="silam_hires_pollen_v6_1",
        file="silam_hires_pollen_v6_1_best.ncd",
        label="SILAM Finland (v6.1)",
        probe_priority=10,
        ui_enabled=True,
        ui_requires_probe=True,   # показываем в UI только если доступен по координатам
        ui_order=10,
    ),
}


def dataset_base_url(dataset_name: str) -> str:
    """Строит NCSS grid base_url по имени датасета (silam_...)."""
    meta = DATASETS[dataset_name]  # KeyError = проблема конфигурации/опечатка
    return f"{THREDDS_NCSS_GRID_BASE}/{meta.path}/{meta.file}"


def iter_datasets_for_probe() -> tuple[str, ...]:
    """Возвращает датасеты в порядке приоритета для SMART-probe по координатам."""
    items = [(name, meta) for name, meta in DATASETS.items() if meta.probe_priority is not None]
    items.sort(key=lambda x: x[1].probe_priority)  # меньше = выше приоритет
    return tuple(name for name, _ in items)


# ---------------------------------------------------------------------------
# Базовые URL (оставляем как публичный API для остального кода)
# ---------------------------------------------------------------------------

BASE_URL_EUROPE_V6_1 = dataset_base_url("silam_europe_pollen_v6_1")
BASE_URL_EUROPE_V6_0 = dataset_base_url("silam_europe_pollen_v6_0")
BASE_URL_REGIONAL_V5_9_1 = dataset_base_url("silam_regional_pollen_v5_9_1")
BASE_URL_HIRES_V6_1 = dataset_base_url("silam_hires_pollen_v6_1")


# ---------------------------------------------------------------------------
# Короткие ключи источников для SMART-склейки (raw_merged[*]["s"] и merged["src"])
# Значения src задаём явно в DATASETS, а здесь оставляем удобный словарь.
# ---------------------------------------------------------------------------

DATASET_SRC_KEYS = {name: meta.src for name, meta in DATASETS.items()}


# Маппинг типов пыльцы: ключ – внутреннее название, значение – дефолтное (англ.) имя
VAR_OPTIONS = {
    "alder_m22": "alder",
    "birch_m22": "birch",
    "grass_m32": "grass",
    "hazel_m23": "hazel",
    "mugwort_m18": "mugwort",
    "olive_m28": "olive",
    "ragweed_m18": "ragweed",
}

URL_VAR_MAPPING = {
    "alder_m22": "cnc_POLLEN_ALDER_m22",
    "birch_m22": "cnc_POLLEN_BIRCH_m22",
    "grass_m32": "cnc_POLLEN_GRASS_m32",
    "hazel_m23": "cnc_POLLEN_HAZEL_m23",
    "mugwort_m18": "cnc_POLLEN_MUGWORT_m18",
    "olive_m28": "cnc_POLLEN_OLIVE_m28",
    "ragweed_m18": "cnc_POLLEN_RAGWEED_m18",
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
    5: "very_high",
}

RESPONSIBLE_MAPPING = {
    -1: "missing",
    1: "alder",
    2: "birch",
    3: "grass",
    4: "olive",
    5: "mugwort",
    6: "ragweed",
    7: "hazel",
}
