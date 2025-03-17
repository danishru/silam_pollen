"""
pollen_forecast.py

Сенсор прогноза уровня пыльцы для интеграции SILAM Pollen.
Использует координатор для обновления данных. Динамически формирует прогноз на основе данных из запроса API.
Преобразует температуру из Кельвина в Цельсий.
"""

import logging
import statistics  # Для вычисления медианы и других статистических функций
from datetime import datetime, timedelta, timezone
from homeassistant.components.weather import WeatherEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
try:
    from homeassistant.components.weather.const import SUPPORT_FORECAST_HOURLY, SUPPORT_FORECAST_TWICE_DAILY
except ImportError:
    SUPPORT_FORECAST_HOURLY = 2
    SUPPORT_FORECAST_TWICE_DAILY = 4
from .const import DOMAIN, INDEX_MAPPING, RESPONSIBLE_MAPPING

_LOGGER = logging.getLogger(__name__)


class PollenForecastSensor(CoordinatorEntity, WeatherEntity):
    """Сенсор прогноза уровня пыльцы для интеграции SILAM Pollen."""

    # Поддерживаются только почасовой и прогноз дважды в день
    _attr_supported_features = SUPPORT_FORECAST_HOURLY | SUPPORT_FORECAST_TWICE_DAILY
    _attr_native_temperature_unit = "°C"

    def __init__(self, coordinator, entry_id: str, base_device_name: str):
        """
        Инициализация сенсора прогноза уровня пыльцы.

        :param coordinator: Экземпляр координатора, который будет обновлять данные.
        :param entry_id: Уникальный идентификатор записи.
        :param base_device_name: Имя устройства (записи), используется для формирования имени сенсора.
        """
        CoordinatorEntity.__init__(self, coordinator)
        WeatherEntity.__init__(self)
        self._entry_id = entry_id
        self._base_device_name = base_device_name
        # Убираем поддержку daily-прогноза – остаётся только почасовой и twice_daily
        self._forecast_hourly = []
        self._extra_attributes = {}  # Инициализируем словарь дополнительных атрибутов
        self._attr_name = f"{self._base_device_name} Forecast"
        self._attr_translation_key = "index_polen_weather"
        from homeassistant.helpers.device_registry import DeviceInfo
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Возвращает дополнительные атрибуты сенсора."""
        return self._extra_attributes

    async def async_added_to_hass(self) -> None:
        """Вызывается после добавления сенсора в HA. Немедленно обновляем прогноз."""
        await super().async_added_to_hass()
        await self._handle_coordinator_update()

    @property
    def unique_id(self) -> str:
        """Возвращает уникальный идентификатор для этой сущности."""
        return f"{self._entry_id}_pollen_forecast"

    @property
    def state(self) -> str | None:
        """
        Возвращает текущее состояние – значение 'condition'
        из первого элемента почасового прогноза.
        """
        if self._forecast_hourly:
            return self._forecast_hourly[0].get("condition")
        return None

    async def _handle_coordinator_update(self) -> None:
        """
        Обработчик обновления данных от координатора.

        Реализована логика формирования почасового прогноза:
          - Сначала собираются все записи из API (элементы stationFeature из coordinator.data["index"]).
          - Затем данные фильтруются так, чтобы оставить только записи для следующих 24 часов (не включая текущий момент).
          - Далее данные агрегируются в не перекрывающиеся окна (размер окна 3, шаг 3),
            что даёт 8 значений (24 часа / 3 = 8).
          - Для каждого окна вычисляется медианный индекс пыльцы (POLI), а для температуры:
              native_temperature – максимальное значение,
              native_templow – минимальное значение.
          - В качестве времени прогноза берётся время медианного элемента окна, но затем оно заменяется на фиксированное,
            зависящее от того, является ли период дневным или ночным, согласно локальному времени:
                - Если дневное (локальный час от 06:00 до 18:00) – время фиксируется на 12:00.
                - Если ночное – время фиксируется на 00:00 (если наблюдаются часы ≥18:00, время устанавливается для следующего дня).
          - Фиксированное время преобразуется в формат ISO с указанием часового пояса UTC.
          - Полученное значение индекса преобразуется в условие (condition) через INDEX_MAPPING.
        """
        _LOGGER.debug("PollenForecastSensor: вызов _handle_coordinator_update")
        now = datetime.utcnow()

        # Обработка почасового прогноза (для SUPPORT_FORECAST_HOURLY)
        self._forecast_hourly = []
        index_data = self.coordinator.data.get("index")
        if index_data is not None:
            station_features = index_data.findall(".//stationFeature")
            if station_features:
                # Собираем "сырые" данные
                raw_hourly = []
                for feature in station_features:
                    forecast_date = feature.get("date")
                    # Преобразуем температуру из Кельвина в Цельсий
                    temp_elem = feature.find(".//data[@name='temp_2m']")
                    try:
                        temp_value = float(temp_elem.text) - 273.15 if temp_elem is not None else None
                    except (ValueError, TypeError):
                        temp_value = None
                    poli_elem = feature.find(".//data[@name='POLI']")
                    try:
                        index_value = int(float(poli_elem.text)) if poli_elem is not None else None
                    except (ValueError, TypeError):
                        index_value = None
                    raw_hourly.append({
                        "datetime": forecast_date or (now.isoformat() + "Z"),
                        "temperature": temp_value,
                        "pollen_index": index_value,
                    })

                # Фильтруем данные для следующих 24 часов
                filtered_hourly = []
                for item in raw_hourly:
                    dt_str = item["datetime"].rstrip("Z")
                    try:
                        dt = datetime.fromisoformat(dt_str)
                    except Exception:
                        dt = now
                    if dt > now and dt <= now + timedelta(hours=24):
                        filtered_hourly.append(item)
                raw_hourly = filtered_hourly

                # Агрегирование в окна по 3 часа (24/3 = 8 значений)
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
                        "pollen_index": median_index,
                    })
                self._forecast_hourly = aggregated_hourly

                # Дополнительный атрибут из первого stationFeature
                additional_feature = station_features[0]
                polisrc_elem = additional_feature.find(".//data[@name='POLISRC']")
                if polisrc_elem is not None:
                    try:
                        re_value = int(float(polisrc_elem.text))
                    except (ValueError, TypeError):
                        re_value = None
                    self._extra_attributes["responsible_elevated"] = RESPONSIBLE_MAPPING.get(re_value, "unknown")
            else:
                _LOGGER.debug("В ответе API нет записей для stationFeature")
        else:
            _LOGGER.error("Нет данных от координатора для формирования почасового прогноза")

        self.async_write_ha_state()

    async def async_forecast_hourly(self) -> list[dict] | None:
        """Возвращает почасовой прогноз."""
        return self._forecast_hourly

    async def async_forecast_twice_daily(self) -> list[dict] | None:
        """
        Возвращает прогноз два раза в день (FORECAST_TWICE_DAILY) на основе реальных данных за следующие 36 часов.

        Реализация:
          - Собираются сырые почасовые данные из API (аналогично предыдущей обработке).
          - Фильтруются записи для следующих 36 часов (не включая текущий момент).
          - Данные делятся на 3 равные группы по 12 часов.
          - Для каждой группы вычисляются:
                - native_temperature: максимальное значение температуры,
                - native_templow: минимальное значение температуры,
                - pollen_index: медианное значение.
          - Вместо динамического времени, для каждой группы назначается фиксированное время:
                - Если группа относится к дневному периоду (локальный час от 06:00 до 18:00) – время устанавливается на 12:00.
                - Если группа относится к ночному периоду – время устанавливается на 00:00. При необходимости, если часы ≥18:00, время фиксируется для следующего дня.
          - Фиксированное время преобразуется в ISO формат с таймзоной UTC.
        """
        now = datetime.utcnow()
        index_data = self.coordinator.data.get("index")
        if index_data is None:
            _LOGGER.error("Нет данных от координатора для формирования прогнозов два раза в день")
            return None
        station_features = index_data.findall(".//stationFeature")
        if not station_features:
            _LOGGER.debug("В ответе API нет записей для stationFeature")
            return None

        # Собираем "сырые" почасовые данные как datetime-объекты
        raw_hourly = []
        for feature in station_features:
            dt_str = feature.get("date")
            try:
                dt = datetime.fromisoformat(dt_str.rstrip("Z"))
            except Exception:
                continue
            if dt <= now or dt > now + timedelta(hours=36):
                continue
            temp_elem = feature.find(".//data[@name='temp_2m']")
            try:
                temp_value = float(temp_elem.text) - 273.15 if temp_elem is not None else None
            except (ValueError, TypeError):
                temp_value = None
            poli_elem = feature.find(".//data[@name='POLI']")
            try:
                index_value = int(float(poli_elem.text)) if poli_elem is not None else None
            except (ValueError, TypeError):
                index_value = None
            raw_hourly.append({
                "datetime": dt,
                "temperature": temp_value,
                "pollen_index": index_value,
            })

        # Разбиваем данные на 3 равные группы по 12 часов
        interval_hours = 12
        forecast_entries = []
        # Получаем локальную таймзону из системы
        local_tz = datetime.now().astimezone().tzinfo
        for i in range(0, 36, interval_hours):
            start = now + timedelta(hours=i)
            end = now + timedelta(hours=i + interval_hours)
            group = [item for item in raw_hourly if start < item["datetime"] <= end]
            if group:
                temps = [item["temperature"] for item in group if item["temperature"] is not None]
                indices = [item["pollen_index"] for item in group if item["pollen_index"] is not None]
                if temps and indices:
                    max_temp = max(temps)
                    min_temp = min(temps)
                    median_index = statistics.median(indices)
                    group_sorted = sorted(group, key=lambda x: x["datetime"])
                    rep_dt = group_sorted[len(group_sorted) // 2]["datetime"]
                    # Переводим представительное время в локальное время
                    local_rep_dt = rep_dt.replace(tzinfo=timezone.utc).astimezone(local_tz)
                    # Определяем, является ли период дневным: если локальный час в диапазоне 06:00–18:00, то дневной
                    if 6 <= local_rep_dt.hour < 18:
                        fixed_local_dt = local_rep_dt.replace(hour=12, minute=0, second=0, microsecond=0)
                    else:
                        # Если локальный час >=18, ночной прогноз фиксируется на 00:00 следующего дня;
                        # если локальный час <6, фиксируется на 00:00 текущего дня
                        if local_rep_dt.hour >= 18:
                            fixed_local_dt = (local_rep_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        else:
                            fixed_local_dt = local_rep_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    # Преобразуем фиксированное локальное время в UTC в формате ISO
                    fixed_dt_str = fixed_local_dt.astimezone(timezone.utc).isoformat()
                    condition = INDEX_MAPPING.get(int(round(median_index)), "unknown")
                    # Фиксируем прогноз для группы
                    forecast_entries.append({
                        "datetime": fixed_dt_str,
                        "is_daytime": (6 <= fixed_local_dt.hour < 18),
                        "condition": condition,
                        "native_temperature": max_temp,
                        "native_templow": min_temp,
                        "pollen_index": median_index
                    })
        forecast_entries.sort(key=lambda x: x["datetime"])
        return forecast_entries
