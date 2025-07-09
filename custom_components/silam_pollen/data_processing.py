import xml.etree.ElementTree as ET
import statistics, math
from datetime import datetime, timedelta, timezone
from math import ceil
from .const import INDEX_MAPPING, URL_VAR_MAPPING

# -------------------------------------------------------------------------
# 0) ВСПОМОГАТЕЛЬНАЯ «СТУПЕНЧАТАЯ» ФУНКЦИЯ ПРОЦЕНТИЛЯ ----------------------
# -------------------------------------------------------------------------
def obs_percentile(sorted_vals: list[float], p: float) -> float:
    """
    «Наблюдательный» процентиль: берёт *реальное* значение из списка,
    без интерполяции между точками (ceil-индекс).

    Аргументы:
        • sorted_vals — ПРЕДВАРИТЕЛЬНО ОТСОРТИРОВАННЫЙ (!) список чисел
        • p           — доля (0.0 … 1.0)

    Возвращает само значение из списка.
    """
    if not sorted_vals:
        raise ValueError("empty list")
    k = ceil(p * len(sorted_vals)) - 1          # 0-based индекс
    return sorted_vals[min(k, len(sorted_vals) - 1)]


# =========================================================================
# merge_station_features()
# =========================================================================
def merge_station_features(
    index_xml: ET.Element,
    main_xml:  ET.Element | None = None,
    *,
    forecast_enabled:   bool        = False,
    selected_allergens: list[str]   = None,
    forecast_duration:  int         = 36,
) -> dict:
    """
    Объединяет данные из XML-ответов для 'index' и 'main' по атрибуту date и формирует итоговый словарь.
    
    Если forecast_enabled=True, дополнительно производится агрегация прогнозных данных.
    Если selected_allergens задан, для каждого выбранного аллергена (например, ['alder_m22', 'birch_m22'])
    рассчитываются агрегированные значения и сразу встраиваются в прогнозы.
    
    Итоговая структура:
    {
        "now": { ... },                  # Запись с самой ранней датой (текущая)
        "hourly_forecast": [ ... ],      # Почасовой прогноз с дополнительно добавленными ключами аллергенов
        "twice_daily_forecast": [ ... ]  # Прогноз дважды в день с дополнительно добавленными ключами аллергенов
        "daily_forecast": [...]          # Суточный прогноз (+ аллергены)
    }
    :param index_xml: XML-дерево, полученное из data["index"]
    :param main_xml: XML-дерево, полученное из data["main"] (может быть None)
    :param forecast_enabled: Флаг, указывающий, нужно ли выполнять агрегацию прогнозных данных.
    :param selected_allergens: Список выбранных аллергенов (например, ['alder_m22', 'birch_m22']).
    :param forecast_duration: Длительность прогноза в часах для прогнозов (используется вместо фиксированных 36 ч).
    :return: Итоговый словарь агрегированных данных.
    """

    # ---------------------------------------------------------------------
    # 1) ПАРСИНГ XML → словари --------------------------------------------
    # ---------------------------------------------------------------------
    def parse_features(xml_root: ET.Element) -> dict:
        features = {}
        for feat in xml_root.findall(".//stationFeature"):
            date = feat.get("date")
            st   = feat.find("station")

            # --- данные станции ------------------------------------------
            st_data = {}
            if st is not None:
                st_data = {
                    "name":      st.get("name"),
                    "latitude":  st.get("latitude"),
                    "longitude": st.get("longitude"),
                    "altitude":  st.get("altitude"),
                }

            # --- данные измерений ----------------------------------------
            data = {}
            for d in feat.findall("data"):
                data[d.get("name")] = {"value": d.text, "units": d.get("units")}

            features[date] = {"station": st_data, "data": data}
        return features

    def parse_iso(s: str) -> datetime:
        """Преобразует ISO-строку (с/без 'Z') в datetime (naïve)."""
        return datetime.fromisoformat(s.rstrip("Z"))

    # ---------------------------------------------------------------------
    # 2) СУТОЧНЫЙ «ПЛАВНЫЙ» POLLEN_INDEX ----------------------------------
    # ---------------------------------------------------------------------
    def calc_smoothed_pollen_index(indices: list[int | float | None]) -> int | None:
        """
        Возвращает сглаженный *pollen_index* (целое) или ``None``.

        ┌────────────────────────────┬────────────────────────────┐
        │ Кол-во точек за окно       │ Используемый показатель    │
        ├────────────────────────────┼────────────────────────────┤
        │ ≥ 18  (≈ 75 %)             │ 80-й процентиль (obs)      │
        │ 12 – 17                    │ 70-й процентиль (obs)      │
        │ < 12                       │ максимум                   │
        └────────────────────────────┴────────────────────────────┘
        """
        clean = [v for v in indices if v is not None]
        if not clean:
            return None

        vals = sorted(clean)
        if len(vals) >= 18:
            pct_val = obs_percentile(vals, 0.80)
        elif len(vals) >= 12:
            pct_val = obs_percentile(vals, 0.70)
        else:
            pct_val = vals[-1]                       # fallback → max

        return int(math.ceil(pct_val))

    # ---------------------------------------------------------------------
    # 3) АЛЛЕРГЕНЫ: «ПЛАВНЫЙ» УРОВЕНЬ + ПИК -------------------------------
    # ---------------------------------------------------------------------
    def calc_allergen_summary(group: list[dict], allergens: list[str]) -> tuple[dict, dict]:
        """
        Для переданной группы записей возвращает
            • levels  — сглаженный уровень (ключи pollen_*),
            • peaks   — пики {'birch': {'peak': int, 'time': iso}, ...}.
        """
        levels, peaks = {}, {}

        for orig in allergens:
            key = f"pollen_{orig.split('_')[0].lower()}"
            vals = [
                g["allergens"][key]
                for g in group
                if g["allergens"].get(key) is not None
            ]

            # --- уровень --------------------------------------------------
            if not vals:
                levels[key] = None
                continue

            vals_sorted = sorted(vals)
            if len(vals_sorted) >= 18:
                pct_val = obs_percentile(vals_sorted, 0.80)
            elif len(vals_sorted) >= 12:
                pct_val = obs_percentile(vals_sorted, 0.70)
            else:
                pct_val = vals_sorted[-1]
            levels[key] = int(math.ceil(pct_val))

            # --- пик (только >0) -----------------------------------------
            if any(v > 0 for v in vals_sorted):
                peak_item = max(
                    (g for g in group if g["allergens"].get(key) is not None),
                    key=lambda x: x["allergens"][key],
                )
                peaks[key.split("_")[1]] = {
                    "peak": peak_item["allergens"][key],
                    "time": peak_item["dt_obj"]
                            .replace(tzinfo=timezone.utc)
                            .isoformat(),
                }

        return levels, peaks

    # ---------------------------------------------------------------------
    # 4) ОБЪЕДИНЯЕМ index + main по дате ----------------------------------
    # ---------------------------------------------------------------------
    idx  = parse_features(index_xml) if index_xml is not None else {}
    main = parse_features(main_xml)  if main_xml  is not None else {}

    raw_merged = {}
    for date in set(idx) | set(main):
        st_idx  = idx.get(date, {}).get("station", {})
        st_main = main.get(date, {}).get("station", {})
        # высота из main имеет приоритет, если не 0
        station = st_main if st_main.get("altitude") not in (None, "0", 0) else st_idx
        raw_merged[date] = {
            "station": station,
            "data": {**idx.get(date, {}).get("data", {}),
                     **main.get(date, {}).get("data", {})}
        }

    # ---------------------------------------------------------------------
    # 5) «NOW» — самая ранняя точка ---------------------------------------
    # ---------------------------------------------------------------------
    now_record, earliest = {}, None
    if raw_merged:
        try:
            earliest = min(raw_merged, key=parse_iso)
        except Exception:
            earliest = next(iter(raw_merged))
        dt_now = parse_iso(earliest).replace(tzinfo=timezone.utc)
        now_record = raw_merged[earliest] | {"date": dt_now.isoformat()}

    # ---------------------------------------------------------------------
    # 6) Если прогноз не требуется — возвращаем только NOW ----------------
    # ---------------------------------------------------------------------
    if not (forecast_enabled and index_xml is not None):
        return {"now": now_record,
                "hourly_forecast": [],
                "twice_daily_forecast": [],
                "daily_forecast": []}

    # ---------------------------------------------------------------------
    # 7) PREP: превращаем сырые точки в список ----------------------------
    # ---------------------------------------------------------------------
    current_time = datetime.utcnow()
    raw_all = []
    for dt_s, entry in raw_merged.items():
        dt = parse_iso(dt_s)

        # --- температура --------------------------------------------------
        t_val = entry["data"].get("temp_2m", {}).get("value")
        temp  = float(t_val) - 273.15 if t_val not in (None, "") else None

        # --- общий POLI ---------------------------------------------------
        poli  = entry["data"].get("POLI", {}).get("value")
        idx_val = int(float(poli)) if poli not in (None, "") else None

        # --- аллергены ----------------------------------------------------
        allergens = {}
        if selected_allergens:
            for orig in selected_allergens:
                real = URL_VAR_MAPPING.get(orig, orig)
                key  = f"pollen_{orig.split('_')[0].lower()}"
                v    = entry["data"].get(real, {}).get("value")
                allergens[key] = int(float(v)) if v not in (None, "") else None

        raw_all.append({
            "datetime": dt_s,
            "dt_obj":  dt,
            "temperature": round(temp, 1) if temp is not None else None,
            "pollen_index": idx_val,
            "allergens": allergens,
        })

    raw_all.sort(key=lambda x: x["dt_obj"])

    # ---------------------------------------------------------------------
    # 8) HOURLY FORECAST – окна по 3 ч (24 ч вперёд) ----------------------
    # ---------------------------------------------------------------------
    hourly_forecast = []
    win, step = 3, 3
    raw_hourly = [
        r for r in raw_all
        if current_time < r["dt_obj"] <= current_time + timedelta(hours=24)
    ]

    for i in range(0, len(raw_hourly) - win + 1, step):
        w = raw_hourly[i:i + win]
        temps = [r["temperature"] for r in w if r["temperature"] is not None]
        idxs  = [r["pollen_index"] for r in w if r["pollen_index"] is not None]

        rep_time = w[1]["datetime"] if len(w) >= 2 else w[0]["datetime"]
        rep_iso  = parse_iso(rep_time).replace(tzinfo=timezone.utc).isoformat()

        # используем максимум вместо медианы для индекса
        peak_idx = max(idxs) if idxs else None

        entry = {
            "datetime": rep_iso,
            "condition": INDEX_MAPPING.get(peak_idx, "unknown"),
            "native_temperature": max(temps) if temps else None,
            "native_temperature_unit": "°C",
            "pollen_index": peak_idx,
            "temperature": max(temps) if temps else None,
        }

        # --- сглаженные аллергены (медиана) ------------------------------
        if selected_allergens:
            for orig in selected_allergens:
                key = f"pollen_{orig.split('_')[0].lower()}"
                vals = [
                    r["allergens"].get(key)
                    for r in w
                    if r["allergens"].get(key) is not None
                ]
                if vals:
                    entry[key] = max(vals)

        hourly_forecast.append(entry)

    # ---------------------------------------------------------------------
    # 9) TWICE-DAILY FORECAST – интервалы по 12 ч -------------------------
    # ---------------------------------------------------------------------
    twice_daily_forecast, seen_twice_dt = [], set()
    raw_twice = [
        r for r in raw_all
        if current_time < r["dt_obj"] <= current_time + timedelta(hours=forecast_duration)
    ]

    local_tz = datetime.now().astimezone().tzinfo

    for offset in range(0, forecast_duration, 12):
        start = current_time + timedelta(hours=offset)
        end   = start + timedelta(hours=12)
        group = [g for g in raw_twice if start < g["dt_obj"] <= end]
        if not group:
            continue

        temps = [g["temperature"]  for g in group if g["temperature"]  is not None]
        idxs  = [g["pollen_index"] for g in group if g["pollen_index"] is not None]
        if not (temps and idxs):
            continue

        smooth_idx = calc_smoothed_pollen_index(idxs)

        # --- репрезентативное время → 00 или 12 (лок) --------------------
        rep_dt  = sorted(group, key=lambda x: x["dt_obj"])[len(group)//2]["dt_obj"]
        local   = rep_dt.astimezone(local_tz)
        if 6 <= local.hour < 18:                     # дневное окно
            fixed_local = local.replace(hour=12, minute=0, second=0, microsecond=0)
        else:                                       # ночное окно
            fixed_local = (
                (local if local.hour < 18 else local + timedelta(days=1))
                .replace(hour=0, minute=0, second=0, microsecond=0)
            )

        fixed_iso = fixed_local.astimezone(timezone.utc).isoformat()
        if fixed_iso in seen_twice_dt:              # защита от дубликатов
            continue
        seen_twice_dt.add(fixed_iso)

        entry = {
            "datetime": fixed_iso,
            "is_daytime": 6 <= fixed_local.hour < 18,
            "condition": INDEX_MAPPING.get(smooth_idx, "unknown"),
            "native_temperature": round(max(temps), 1),
            "native_templow":     round(min(temps), 1),
            "pollen_index":       smooth_idx,
            "temperature":        round(max(temps), 1),
            "allergen_peaks": {},
        }

        # --- аллергены: уровень + пик ------------------------------------
        if selected_allergens:
            levels, peaks = calc_allergen_summary(group, selected_allergens)
            entry.update(levels)
            entry["allergen_peaks"] = peaks

        twice_daily_forecast.append(entry)

    twice_daily_forecast.sort(key=lambda x: x["datetime"])

    # ---------------------------------------------------------------------
    # 10) DAILY FORECAST – окна по 24 ч -----------------------------------
    # ---------------------------------------------------------------------
    daily_forecast = []
    raw_daily = [
        r for r in raw_all
        if current_time < r["dt_obj"] <= current_time + timedelta(hours=forecast_duration)
    ]

    total_days = math.ceil(forecast_duration / 24)
    for d in range(1, total_days + 1):               # начинаем с «завтра»
        day_start = (current_time + timedelta(days=d)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        group = [
            g for g in raw_daily
            if day_start < g["dt_obj"] <= day_start + timedelta(days=1)
        ]
        if not group:
            continue

        temps = [g["temperature"]  for g in group if g["temperature"]  is not None]
        idxs  = [g["pollen_index"] for g in group if g["pollen_index"] is not None]

        smooth_idx = calc_smoothed_pollen_index(idxs)
        rep_noon   = (day_start + timedelta(hours=12)).astimezone(local_tz)

        entry = {
            "datetime":           rep_noon.astimezone(timezone.utc).isoformat(),
            "condition":          INDEX_MAPPING.get(smooth_idx, "unknown"),
            "native_temperature": max(temps) if temps else None,
            "native_templow":     min(temps) if temps else None,
            "pollen_index":       smooth_idx,
            "temperature":        max(temps) if temps else None,
            "allergen_peaks": {},
        }

        # --- аллергены: уровень + пик ------------------------------------
        if selected_allergens:
            levels, peaks = calc_allergen_summary(group, selected_allergens)
            entry.update(levels)
            entry["allergen_peaks"] = peaks

        daily_forecast.append(entry)

    # -----------------------------------------------------------------
    # 11) ДОСТУПНЫЙ ГОРИЗОНТ ПРОГНОЗА ----------------------------------
    # -----------------------------------------------------------------
    try:
        if raw_all:
            # последний прогноз — из raw_all, делаем его timezone-aware
            last_dt = raw_all[-1]["dt_obj"].replace(tzinfo=timezone.utc)
            # dt_now уже timezone-aware из шага 5
            forecast_horizon  = round(
                (last_dt - dt_now).total_seconds() / 3600.0,
                2
            )
        else:
            forecast_horizon  = None
    except Exception:
        forecast_horizon  = None

    # ---------------------------------------------------------------------
    # 12) ФИНАЛЬНЫЙ ВОЗВРАТ ----------------------------------------------
    # ---------------------------------------------------------------------
    return {
        "now": now_record,
        "hourly_forecast":      hourly_forecast,
        "twice_daily_forecast": twice_daily_forecast,
        "daily_forecast":       daily_forecast,
        "forecast_horizon":   forecast_horizon,
    }