import xml.etree.ElementTree as ET
import statistics
import math
from datetime import datetime, timedelta, timezone
from .const import INDEX_MAPPING, URL_VAR_MAPPING

def merge_station_features(index_xml: ET.Element, main_xml: ET.Element = None, forecast_enabled: bool = False, selected_allergens: list = None) -> dict:
    """
    Объединяет данные из XML-ответов для 'index' и 'main' по атрибуту date и формирует итоговый словарь.
    
    Если forecast_enabled=True, дополнительно производится агрегация прогнозных данных.
    Если selected_allergens задан, для каждого выбранного аллергена (например, ['alder_m22', 'birch_m22'])
    рассчитываются агрегированные значения и сразу встраиваются в прогнозы.
    
    Итоговая структура:
      {
         "now": { ... },                  # Запись с самой ранней датой (текущая)
         "hourly_forecast": [ ... ],      # Почасовой прогноз с дополнительно добавленными ключами аллергенов
         "twice_daily_forecast": [ ... ]  # Прогноз два раза в день с дополнительно добавленными ключами аллергенов
      }
    :param index_xml: XML-дерево, полученное из data["index"]
    :param main_xml: XML-дерево, полученное из data["main"] (может быть None)
    :param forecast_enabled: Флаг, указывающий, нужно ли выполнять агрегацию прогнозных данных.
    :param selected_allergens: Список выбранных аллергенов (например, ['alder_m22', 'birch_m22']).
    :return: Итоговый словарь агрегированных данных.
    """
    def parse_features(xml_root: ET.Element) -> dict:
        """
        Парсит XML-дерево и формирует словарь с данными для каждой станции по дате.
        """
        features = {}
        for feature in xml_root.findall(".//stationFeature"):
            date = feature.get("date")
            # Извлекаем информацию о станции
            station_elem = feature.find("station")
            station_data = {}
            if station_elem is not None:
                station_data = {
                    "name": station_elem.get("name"),
                    "latitude": station_elem.get("latitude"),
                    "longitude": station_elem.get("longitude"),
                    "altitude": station_elem.get("altitude")
                }
            # Извлекаем все элементы <data> и их значения
            data_elements = {}
            for data_elem in feature.findall("data"):
                key = data_elem.get("name")
                data_elements[key] = {
                    "value": data_elem.text,
                    "units": data_elem.get("units")
                }
            features[date] = {
                "station": station_data,
                "data": data_elements
            }
        return features

    def parse_iso(date_str: str) -> datetime:
        """
        Преобразует строку даты в объект datetime, удаляя завершающую "Z", если она присутствует.
        """
        return datetime.fromisoformat(date_str.rstrip("Z"))
    
    # Парсим XML-деревья для index и main (если задано)
    index_features = parse_features(index_xml) if index_xml is not None else {}
    main_features = parse_features(main_xml) if main_xml is not None else {}

    # Объединяем данные по датам из index и main
    raw_merged = {}
    all_dates = set(index_features.keys()) | set(main_features.keys())
    for date in all_dates:
        station_index = index_features.get(date, {}).get("station", {})
        station_main = main_features.get(date, {}).get("station", {})
        # Если в main указана ненулевая высота, отдаём ей предпочтение
        station = station_main if station_main.get("altitude") not in (None, "0", 0) else station_index
        data_index = index_features.get(date, {}).get("data", {})
        data_main = main_features.get(date, {}).get("data", {})
        combined_data = {**data_index, **data_main}
        raw_merged[date] = {
            "station": station,
            "data": combined_data
        }
    
    # Выбираем запись "now" – с самой ранней датой
    now_record = {}
    if raw_merged:
        try:
            sorted_dates = sorted(raw_merged.keys(), key=lambda d: parse_iso(d))
        except Exception:
            sorted_dates = list(raw_merged.keys())
        earliest = sorted_dates[0]
        now_record = raw_merged[earliest]
        now_record["date"] = earliest
    else:
        earliest = None

    # Инициализируем списки агрегированных прогнозов
    hourly_forecast = []
    twice_daily_forecast = []

    if forecast_enabled and index_xml is not None:
        current_time = datetime.utcnow()
        # Собираем "сырые" данные из raw_merged с предварительным сохранением объекта datetime и значений аллергенов
        raw_all = []
        for date_str, entry in raw_merged.items():
            dt_obj = parse_iso(date_str)
            # Вычисляем температуру (перевод из Кельвина в Цельсий)
            temp_value = None
            if "temp_2m" in entry["data"] and entry["data"]["temp_2m"]["value"] is not None:
                try:
                    temp_value = float(entry["data"]["temp_2m"]["value"]) - 273.15
                except (ValueError, TypeError):
                    temp_value = None
            # Индекс пыльцы для общего поля POLI
            pollen_index = None
            if "POLI" in entry["data"] and entry["data"]["POLI"]["value"] is not None:
                try:
                    pollen_index = int(float(entry["data"]["POLI"]["value"]))
                except (ValueError, TypeError):
                    pollen_index = None
            # Если выбраны отдельные аллергены, пытаемся извлечь их значения
            allergens_values = {}
            if selected_allergens:
                for orig_allergen in selected_allergens:
                    real_key = URL_VAR_MAPPING.get(orig_allergen, orig_allergen)
                    forecast_key = "pollen_" + orig_allergen.split('_')[0].lower()
                    if real_key in entry["data"] and entry["data"][real_key]["value"] is not None:
                        try:
                            allergens_values[forecast_key] = int(float(entry["data"][real_key]["value"]))
                        except (ValueError, TypeError):
                            allergens_values[forecast_key] = None
                    else:
                        allergens_values[forecast_key] = None

            raw_all.append({
                "datetime": date_str,
                "dt_obj": dt_obj,
                "temperature": round(temp_value, 1) if temp_value is not None else None,
                "pollen_index": pollen_index,
                "allergens": allergens_values  # Словарь с данными по каждому аллергену
            })
        try:
            raw_all.sort(key=lambda item: item["dt_obj"])
        except Exception:
            pass

        # Почасовой прогноз – окна по 3 часа (на следующие 24 часа)
        window_size = 3
        step = 3
        raw_hourly = [item for item in raw_all if item["dt_obj"] > current_time and item["dt_obj"] <= current_time + timedelta(hours=24)]
        for i in range(0, len(raw_hourly) - window_size + 1, step):
            window = raw_hourly[i:i+window_size]
            temps = [item["temperature"] for item in window if item["temperature"] is not None]
            indices = [item["pollen_index"] for item in window if item["pollen_index"] is not None]
            max_temp = max(temps) if temps else None
            median_index = statistics.median(indices) if indices else None
            # Выбираем время репрезентативного окна
            rep_time = window[1]["datetime"] if len(window) >= 2 else window[0]["datetime"]
            rep_time_str = parse_iso(rep_time).replace(tzinfo=timezone.utc).isoformat()
            condition = INDEX_MAPPING.get(int(round(median_index)) if median_index is not None else None, "unknown")
            forecast_entry = {
                "datetime": rep_time_str,
                "condition": condition,
                "native_temperature": round(max_temp, 1) if max_temp is not None else None,
                "native_temperature_unit": "°C",
                "pollen_index": int(math.ceil(median_index)) if median_index is not None else None,
                "temperature": round(max_temp, 1) if max_temp is not None else None
            }
            # Встроенная агрегация данных по аллергенам для данного окна
            if selected_allergens:
                for orig_allergen in selected_allergens:
                    forecast_key = "pollen_" + orig_allergen.split('_')[0].lower()
                    allergen_values = [item["allergens"].get(forecast_key) for item in window if item["allergens"].get(forecast_key) is not None]
                    if allergen_values:
                        forecast_entry[forecast_key] = int(math.ceil(statistics.median(allergen_values)))
            hourly_forecast.append(forecast_entry)

        # Прогноз дважды в день – интервалы по 12 часов (на следующие 36 часов)
        raw_twice = [item for item in raw_all if item["dt_obj"] > current_time and item["dt_obj"] <= current_time + timedelta(hours=36)]
        interval_hours = 12
        aggregated_twice = []
        local_tz = datetime.now().astimezone().tzinfo
        for i in range(0, 36, interval_hours):
            start = current_time + timedelta(hours=i)
            end = current_time + timedelta(hours=i + interval_hours)
            group = [item for item in raw_twice if start < item["dt_obj"] <= end]
            if group:
                temps = [item["temperature"] for item in group if item["temperature"] is not None]
                indices = [item["pollen_index"] for item in group if item["pollen_index"] is not None]
                if temps and indices:
                    max_temp = max(temps)
                    min_temp = min(temps)
                    median_index = statistics.median(indices)
                    group_sorted = sorted(group, key=lambda x: x["dt_obj"])
                    rep_dt = group_sorted[len(group_sorted) // 2]["datetime"]
                    local_rep_dt = parse_iso(rep_dt).replace(tzinfo=timezone.utc).astimezone(local_tz)
                    if 6 <= local_rep_dt.hour < 18:
                        fixed_local_dt = local_rep_dt.replace(hour=12, minute=0, second=0, microsecond=0)
                    else:
                        if local_rep_dt.hour >= 18:
                            fixed_local_dt = (local_rep_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        else:
                            fixed_local_dt = local_rep_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    fixed_dt_str = fixed_local_dt.astimezone(timezone.utc).isoformat()
                    condition = INDEX_MAPPING.get(int(round(median_index)), "unknown")
                    forecast_entry = {
                        "datetime": fixed_dt_str,
                        "is_daytime": (6 <= fixed_local_dt.hour < 18),
                        "condition": condition,
                        "native_temperature": round(max_temp, 1) if max_temp is not None else None,
                        "native_templow": round(min_temp, 1) if min_temp is not None else None,
                        "pollen_index": int(math.ceil(median_index)) if median_index is not None else None,
                        "temperature": round(max_temp, 1) if max_temp is not None else None
                    }
                    # Встроенная агрегация данных по аллергенам для данного интервала
                    if selected_allergens:
                        for orig_allergen in selected_allergens:
                            forecast_key = "pollen_" + orig_allergen.split('_')[0].lower()
                            allergen_values = [item["allergens"].get(forecast_key) for item in group if item["allergens"].get(forecast_key) is not None]
                            if allergen_values:
                                forecast_entry[forecast_key] = int(math.ceil(statistics.median(allergen_values)))
                    aggregated_twice.append(forecast_entry)
        aggregated_twice.sort(key=lambda x: x["datetime"])
        twice_daily_forecast = aggregated_twice

    result = {
        "now": now_record,
        "hourly_forecast": hourly_forecast,
        "twice_daily_forecast": twice_daily_forecast
    }
    return result