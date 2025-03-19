import xml.etree.ElementTree as ET
import statistics
from datetime import datetime, timedelta, timezone
from .const import INDEX_MAPPING

def merge_station_features(index_xml: ET.Element, main_xml: ET.Element = None, forecast_enabled: bool = False) -> dict:
    """
    Объединяет данные из XML-ответов для 'index' и 'main' по атрибуту date и формирует итоговый словарь со следующей структурой:
    
      {
         "now": { ... },                  # Запись с самой ранней датой (текущая)
         "hourly_forecast": [ ... ],      # Агрегированные данные почасового прогноза (на следующие 24 часа)
         "twice_daily_forecast": [ ... ]  # Агрегированные данные прогноза два раза в день (на следующие 36 часов)
      }
      
    Если main_xml отсутствует, объединение происходит только на основе index_xml.
    Если forecast_enabled=True, дополнительно производится агрегация прогнозных данных.
    
    :param index_xml: XML-дерево, полученное из data["index"]
    :param main_xml: XML-дерево, полученное из data["main"] (может быть None)
    :param forecast_enabled: Флаг, указывающий, нужно ли выполнять агрегацию прогнозных данных.
    :return: Итоговый словарь с ключами "now", "hourly_forecast" и "twice_daily_forecast" (если прогноз включен).
    """
    def parse_features(xml_root: ET.Element) -> dict:
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
            # Извлекаем все элементы <data>
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

    # Парсим данные из XML
    index_features = parse_features(index_xml) if index_xml is not None else {}
    main_features = parse_features(main_xml) if main_xml is not None else {}

    # Объединяем данные по датам
    raw_merged = {}
    all_dates = set(index_features.keys()) | set(main_features.keys())
    for date in all_dates:
        station_index = index_features.get(date, {}).get("station", {})
        station_main = main_features.get(date, {}).get("station", {})
        # Если в main указана ненулевая высота, отдаём ей предпочтение
        if station_main.get("altitude") not in (None, "0", 0):
            station = station_main
        else:
            station = station_index

        data_index = index_features.get(date, {}).get("data", {})
        data_main = main_features.get(date, {}).get("data", {})
        combined_data = {**data_index, **data_main}
        
        raw_merged[date] = {
            "station": station,
            "data": combined_data
        }
    
    # Выбираем самую раннюю запись для ключа "now"
    now_record = {}
    if raw_merged:
        try:
            sorted_dates = sorted(raw_merged.keys(), key=lambda d: datetime.fromisoformat(d.rstrip("Z")))
        except Exception:
            sorted_dates = list(raw_merged.keys())
        earliest = sorted_dates[0]
        now_record = raw_merged[earliest]
    else:
        earliest = None

    # Если включен режим прогнозов, агрегируем почасовой и прогноз дважды в день
    hourly_forecast = []
    twice_daily_forecast = []
    if forecast_enabled and index_xml is not None:
        current_time = datetime.utcnow()
        # Собираем "сырые" данные из raw_merged (все записи, без ограничения)
        raw_all = []
        for date_str, entry in raw_merged.items():
            temp_value = None
            if "temp_2m" in entry["data"] and entry["data"]["temp_2m"]["value"] is not None:
                try:
                    temp_value = float(entry["data"]["temp_2m"]["value"]) - 273.15
                except (ValueError, TypeError):
                    temp_value = None
            pollen_index = None
            if "POLI" in entry["data"] and entry["data"]["POLI"]["value"] is not None:
                try:
                    pollen_index = int(float(entry["data"]["POLI"]["value"]))
                except (ValueError, TypeError):
                    pollen_index = None

            raw_all.append({
                "datetime": date_str,
                "temperature": temp_value,
                "pollen_index": pollen_index,
            })
        try:
            raw_all.sort(key=lambda item: datetime.fromisoformat(item["datetime"].rstrip("Z")))
        except Exception:
            pass

        # Фильтруем для почасового прогноза: следующие 24 часа
        raw_hourly = [item for item in raw_all if datetime.fromisoformat(item["datetime"].rstrip("Z")) > current_time and
                      datetime.fromisoformat(item["datetime"].rstrip("Z")) <= current_time + timedelta(hours=24)]
        # Агрегируем данные в окна по 3 часа (24/3 = 8 окон)
        window_size = 3
        step = 3
        aggregated_hourly = []
        for i in range(0, len(raw_hourly) - window_size + 1, step):
            window = raw_hourly[i:i+window_size]
            temps = [item["temperature"] for item in window if item["temperature"] is not None]
            indices = [item["pollen_index"] for item in window if item["pollen_index"] is not None]
            max_temp = max(temps) if temps else None
            min_temp = min(temps) if temps else None
            median_index = statistics.median(indices) if indices else None
            rep_time = window[1]["datetime"] if len(window) >= 2 else window[0]["datetime"]
            rep_time_str = datetime.fromisoformat(rep_time.rstrip("Z")).replace(tzinfo=timezone.utc).isoformat()
            condition = INDEX_MAPPING.get(int(round(median_index)) if median_index is not None else None, "unknown")
            aggregated_hourly.append({
                "datetime": rep_time_str,
                "condition": condition,
                "native_temperature": max_temp,
                "native_temperature_unit": "°C",
                "pollen_index": int(round(median_index)) if median_index is not None else None,
            })
        hourly_forecast = aggregated_hourly

        # Фильтруем для прогноза два раза в день: следующие 36 часов
        raw_twice = [item for item in raw_all if datetime.fromisoformat(item["datetime"].rstrip("Z")) > current_time and
                     datetime.fromisoformat(item["datetime"].rstrip("Z")) <= current_time + timedelta(hours=36)]
        # Группируем данные по 12-часовым интервалам (36 часов / 12 = 3 группы)
        interval_hours = 12
        aggregated_twice = []
        local_tz = datetime.now().astimezone().tzinfo
        for i in range(0, 36, interval_hours):
            start = current_time + timedelta(hours=i)
            end = current_time + timedelta(hours=i + interval_hours)
            group = [item for item in raw_twice if start < datetime.fromisoformat(item["datetime"].rstrip("Z")) <= end]
            if group:
                temps = [item["temperature"] for item in group if item["temperature"] is not None]
                indices = [item["pollen_index"] for item in group if item["pollen_index"] is not None]
                if temps and indices:
                    max_temp = max(temps)
                    min_temp = min(temps)
                    median_index = statistics.median(indices)
                    group_sorted = sorted(group, key=lambda x: datetime.fromisoformat(x["datetime"].rstrip("Z")))
                    rep_dt = group_sorted[len(group_sorted) // 2]["datetime"]
                    local_rep_dt = datetime.fromisoformat(rep_dt.rstrip("Z")).replace(tzinfo=timezone.utc).astimezone(local_tz)
                    if 6 <= local_rep_dt.hour < 18:
                        fixed_local_dt = local_rep_dt.replace(hour=12, minute=0, second=0, microsecond=0)
                    else:
                        if local_rep_dt.hour >= 18:
                            fixed_local_dt = (local_rep_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        else:
                            fixed_local_dt = local_rep_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    fixed_dt_str = fixed_local_dt.astimezone(timezone.utc).isoformat()
                    condition = INDEX_MAPPING.get(int(round(median_index)), "unknown")
                    aggregated_twice.append({
                        "datetime": fixed_dt_str,
                        "is_daytime": (6 <= fixed_local_dt.hour < 18),
                        "condition": condition,
                        "native_temperature": max_temp,
                        "native_templow": min_temp,
                        "pollen_index": int(round(median_index)) if median_index is not None else None
                    })
        aggregated_twice.sort(key=lambda x: x["datetime"])
        twice_daily_forecast = aggregated_twice

    result = {
        #"raw": raw_merged,            # сырые объединённые данные (можно удалить, если не нужны)
        "now": now_record,
        "hourly_forecast": hourly_forecast,
        "twice_daily_forecast": twice_daily_forecast
    }
    return result
