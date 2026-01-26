# coordinator.py

"""
Реализует SilamCoordinator для интеграции SILAM Pollen.
Использует DataUpdateCoordinator для обновления данных для всех сенсоров интеграции.

Шаг 1 (аккуратное внедрение):
- Добавлена лёгкая проверка "свежести" через THREDDS runs/catalog.xml.
- На этом шаге информация используется только как диагностика (не влияет на логику фетча).

Шаг 2 (аккуратное внедрение, без лишних изменений):
- Добавлен «инкрементальный» режим: если новый набор данных НЕ появился (run_id не изменился),
  то мы НЕ делаем полный запрос index/main, а пересобираем результат из уже сохранённого raw_merged.
- Шаг 2b (очень аккуратно): добавлена опциональная догрузка «хвоста» в инкрементальном режиме,
  если окно прогноза уехало дальше, чем максимальная дата в кеше.
"""

import math

import logging
import re
import time
import aiohttp
import async_timeout
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import URL_VAR_MAPPING, resolve_silam_var_name  # Импортируем маппинг для преобразования переменных

_LOGGER = logging.getLogger(__name__)

# THREDDS catalog namespace
_THREDDS_NS = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"}


class SilamCoordinator(DataUpdateCoordinator):
    """Координатор для интеграции SILAM Pollen."""

    def __init__(
        self,
        hass,
        base_device_name,
        var_list,
        manual_coordinates,
        manual_latitude,
        manual_longitude,
        desired_altitude,
        update_interval,
        base_url,
        forecast=False,
        forecast_duration: int = 36,
        *,
        dataset_selection="smart",
        smart_candidates=None,
    ):
        """
        Инициализирует координатор.

        :param hass: экземпляр Home Assistant.
        :param base_device_name: имя службы, используемое для формирования имени координатора.
        :param var_list: список переменных (аллергенов), выбранных пользователем.
        :param manual_coordinates: булево значение, использовать ли ручные координаты.
        :param manual_latitude: ручная широта.
        :param manual_longitude: ручная долгота.
        :param desired_altitude: высота над уровнем моря, заданная пользователем.
        :param update_interval: интервал обновления (в минутах).
        :param base_url: базовый URL для запросов.
        :param forecast: включает режим прогноза (определяет длительность запроса).
        :param forecast_duration: длительность прогноза в часах (от 36 до 120).
        :param dataset_selection: политика выбора датасета ('smart' или фиксированный режим).
        :param smart_candidates: список кандидатов base_url для SMART (в порядке приоритета).
        """
        self._base_device_name = base_device_name
        self._log_prefix = f"[{base_device_name}]"
        self._var_list = var_list
        self._manual_coordinates = manual_coordinates
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._desired_altitude = desired_altitude
        self._base_url = base_url

        # ---------------------------------------------------------------------
        # Политика выбора датасета (SMART vs фиксированный)
        # - SMART: координатор при старте может выбрать "лучший" датасет из списка кандидатов.
        # - Фиксированный: используем только текущий base_url, без попыток альтернатив.
        #
        # Сейчас реализуем только выбор "лучшего" датасета при старте/первом обновлении.
        # Догрузку недостающих данных из других наборов добавим позже отдельным шагом.
        # ---------------------------------------------------------------------
        self._dataset_selection = (dataset_selection or "smart").lower()
        self._smart_candidates = list(smart_candidates or [])

        # Если кандидаты не передали — пробуем хотя бы текущий base_url
        if not self._smart_candidates and self._base_url:
            self._smart_candidates = [self._base_url]

        # Текущий base_url оставляем как fallback, но НЕ первым (иначе SMART никогда не переключится)
        if self._base_url and self._base_url not in self._smart_candidates:
            self._smart_candidates.append(self._base_url)

        # Чтобы SMART-выбор выполнялся один раз на жизненный цикл координатора
        self._smart_probe_done = False

        self._forecast_enabled = forecast
        self._forecast_duration = forecast_duration

        # --- THREDDS runs catalog (проверка свежести) ---
        self._runs_catalog_url = self._derive_runs_catalog_url()
        self._latest_run_id = None
        self._latest_run_start = None
        self._latest_run_end = None

        # --- Шаг 2: «активный» run_id, на котором построен текущий кеш raw_merged ---
        # Нужен, чтобы понимать: «набор данных тот же» -> можно пересобрать из кеша без полного запроса.
        self._active_run_id = None

        # Извлекаем версию SILAM из BASE_URL
        match = re.search(r"pollen_v(\d+_\d+(?:_\d+)?)", self._base_url)
        if match:
            self.silam_version = match.group(1)
        else:
            self.silam_version = "unknown"

        # Инициализируем merged_data (будет заполняться после обновления)
        self.merged_data = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"SILAM Pollen Coordinator ({base_device_name})",
            update_interval=timedelta(minutes=update_interval),
            always_update=True,
        )

    async def async_request_refresh(self, context=None):
        """
        Переопределённый метод принудительного обновления.
        Логирует контекст вызова (например, идентификатор сущности, которая запросила обновление).
        """
        _LOGGER.debug("%s Запрошено обновление данных. Контекст: %s", self._log_prefix, context)
        return await super().async_request_refresh()

    def _derive_runs_catalog_url(self):
        """Строит URL runs/catalog.xml по текущему self._base_url (NCSS grid).

        Пример:
          https://.../thredds/ncss/grid/<dataset>/<file>.ncd
          -> https://.../thredds/catalog/<dataset>/runs/catalog.xml
        """
        try:
            u = urlparse(self._base_url)
            parts = [p for p in u.path.split("/") if p]
            # ... thredds / ncss / grid / <dataset> / <file>
            grid_idx = parts.index("grid")
            dataset = parts[grid_idx + 1]
            return f"{u.scheme}://{u.netloc}/thredds/catalog/{dataset}/runs/catalog.xml"
        except Exception:
            return None

    async def _fetch_latest_run_info(self, session):
        """Возвращает (run_id, start, end) из runs/catalog.xml.

        На этом шаге это *только диагностика* (не влияет на логику фетча).
        """
        if not self._runs_catalog_url:
            return None, None, None

        try:
            async with session.get(self._runs_catalog_url) as response:
                if response.status != 200:
                    _LOGGER.debug("%s runs catalog HTTP %s", self._log_prefix, response.status)
                    return None, None, None
                async with async_timeout.timeout(10):
                    xml_text = await response.text()

            root = ET.fromstring(xml_text)
            parent = root.find(".//t:dataset[@name='Forecast Model Run']", _THREDDS_NS)
            latest = parent.find("t:dataset", _THREDDS_NS) if parent is not None else None
            if latest is None:
                return None, None, None

            run_id = latest.get("name")
            start_el = latest.find("t:timeCoverage/t:start", _THREDDS_NS)
            end_el = latest.find("t:timeCoverage/t:end", _THREDDS_NS)
            start = start_el.text.strip() if (start_el is not None and start_el.text) else None
            end = end_el.text.strip() if (end_el is not None and end_el.text) else None
            return run_id, start, end

        except Exception as err:
            _LOGGER.debug("%s Не удалось получить/распарсить runs catalog (%s): %s", self._log_prefix, self._runs_catalog_url, err)
            return None, None, None

    # ---------------------------------------------------------------------
    # SMART-выбор датасета (Шаг 3 — основа под будущие улучшения)
    # ---------------------------------------------------------------------

    def _set_base_url(self, new_base_url: str) -> None:
        """Аккуратно переключает координатор на другой base_url.

        Важно: при смене датасета сбрасываем run_id и кеш merged_data, чтобы не смешивать источники.
        """
        if not new_base_url or new_base_url == self._base_url:
            return

        old = self._base_url
        self._base_url = new_base_url

        # Пересчитываем runs catalog URL и SILAM-версию, так как они зависят от base_url
        self._runs_catalog_url = self._derive_runs_catalog_url()

        match = re.search(r"pollen_v(\d+_\d+(?:_\d+)?)", self._base_url)
        self.silam_version = match.group(1) if match else "unknown"

        # Сбрасываем привязку к активному run_id и кеш, чтобы шаг 2 не использовал старые данные
        self._active_run_id = None
        self.merged_data = {}

        _LOGGER.info("%s SMART: base_url switched: %s -> %s", self._log_prefix, old, new_base_url)

    async def _smart_probe_best_base_url(self, session, latitude, longitude) -> str | None:
        """Проверяет кандидатов и возвращает первый доступный base_url (HTTP 200)."""
        candidates = self._smart_candidates or [self._base_url]
        for url in candidates:
            if not url:
                continue

            # Лёгкий тест-доступности через минимальный запрос NCSS (без прогноза)
            test_url = (
                f"{url}?var=POLI&latitude={latitude}&longitude={longitude}"
                f"&time_start=present&time_duration=PT0H&accept=xml"
            )
            try:
                async with async_timeout.timeout(10):
                    async with session.get(test_url) as resp:
                        if resp.status == 200:
                            return url
            except Exception as err:
                _LOGGER.debug("%s SMART probe failed for %s: %s", self._log_prefix, url, err)

        return None

    async def _apply_smart_selection_if_needed(self, session, latitude, longitude) -> None:
        """Применяет политику SMART: выбирает лучший датасет один раз на старте."""
        if self._dataset_selection != "smart":
            return
        if self._smart_probe_done:
            return

        self._smart_probe_done = True

        chosen = await self._smart_probe_best_base_url(session, latitude, longitude)
        if chosen and chosen != self._base_url:
            self._set_base_url(chosen)

        # Пишем минимальную диагностическую инфу (дальше можно вывести в diagnostics сенсор)
        try:
            if isinstance(self.merged_data, dict):
                self.merged_data["dataset_selection"] = self._dataset_selection
                self.merged_data["effective_base_url"] = self._base_url
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Шаг 2: вспомогательные функции для «инкрементального» режима
    # ---------------------------------------------------------------------

    def _parse_dt_utc(self, dt_str: str):
        """Парсит ISO-строку времени в aware datetime (UTC).

        Поддерживает:
          - ...Z
          - ...+00:00
          - naive (трактуем как UTC)
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                return datetime.fromisoformat(dt_str[:-1]).replace(tzinfo=timezone.utc)
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _build_station_features_xml_from_raw_merged(self, raw_merged: dict) -> ET.Element:
        """Строит минимальный XML в формате NCSS (stationFeature/station/data) из raw_merged.

        Важно: делаем именно тот формат, который ожидает текущий data_processing.parse_features():
        - <stationFeature date="...">
            <station name="..." latitude="..." longitude="..." altitude="..."/>
            <data name="..." units="...">VALUE</data>
          </stationFeature>

        Это позволяет на шаге 2 пересобрать merged_data без полного сетевого фетча.
        """
        root = ET.Element("stationFeatureCollection")

        # сортируем по времени (чтобы «now» вычислялся стабильно)
        def _sort_key(k: str):
            dt = self._parse_dt_utc(k)
            return dt if dt is not None else datetime.min.replace(tzinfo=timezone.utc)

        for dt_s in sorted(raw_merged.keys(), key=_sort_key):
            payload = raw_merged.get(dt_s) or {}
            sf = ET.SubElement(root, "stationFeature", {"date": dt_s})

            station = payload.get("station") or {}
            ET.SubElement(
                sf,
                "station",
                {
                    "name": str(station.get("name", "")),
                    "latitude": str(station.get("latitude", "")),
                    "longitude": str(station.get("longitude", "")),
                    "altitude": str(station.get("altitude", "")),
                },
            )

            data_dict = payload.get("data") or {}
            for var_name, dv in data_dict.items():
                if dv is None:
                    continue
                units = ""
                value = ""
                if isinstance(dv, dict):
                    units = dv.get("units") or ""
                    v = dv.get("value")
                    value = "" if v is None else str(v)
                else:
                    value = str(dv)

                el = ET.SubElement(sf, "data", {"name": str(var_name), "units": str(units)})
                el.text = value

        return root

    def _build_index_url(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсора index.
        Параметры:
          var=POLI
          var=POLISRC
          var=temp_2m
          latitude, longitude
          time_start=present
          time_duration=<значение из параметра self._forecast_duration>
          accept=xml
        """
        time_duration = f"PT{self._forecast_duration}H" if self._forecast_enabled else "PT0H"
        query_params = [
            "var=POLI",
            "var=POLISRC",
            "var=temp_2m",
            f"latitude={latitude}",
            f"longitude={longitude}",
            "time_start=present",
            f"time_duration={time_duration}",
            "accept=xml",
        ]
        url = self._base_url + "?" + "&".join(query_params)
        return url

    def _build_main_url(self, latitude, longitude):
        """
        Формирует URL для запроса данных для сенсоров main.
        Для каждого выбранного аллергена добавляется параметр var с преобразованием через URL_VAR_MAPPING.
        Плюс общие параметры:
          latitude, longitude
          time_start=present
          time_duration=<значение из параметра self._forecast_duration>
          vertCoord=<desired_altitude>
          accept=xml
        """

        time_duration = f"PT{self._forecast_duration}H" if self._forecast_enabled else "PT0H"

        query_params = []
        if self._var_list:
            for allergen in self._var_list:
                full_allergen = resolve_silam_var_name(allergen, self._base_url)
                query_params.append(f"var={full_allergen}")
        query_params.append(f"latitude={latitude}")
        query_params.append(f"longitude={longitude}")
        query_params.append("time_start=present")
        query_params.append(f"time_duration={time_duration}")  # Добавляем параметр времени прогноза
        query_params.append(f"vertCoord={self._desired_altitude}")
        query_params.append("accept=xml")

        url = self._base_url + "?" + "&".join(query_params)
        return url

    async def _async_update_data(self):
        """
        Асинхронно обновляет данные через два HTTP-запроса:
          - Для сенсора index с использованием _build_index_url.
          - Для сенсоров main с использованием _build_main_url (если var_list не пуст).
        Возвращает словарь с ключами 'index' и 'main' (если применимо).
        """
        # Засекаем начало выполнения (_fetch_) всего процесса
        start = time.monotonic()

        # --- Диагностика типа запроса (для SilamPollenFetchDurationSensor) ---
        # full         : обычный полный сетевой фетч index/main
        # synthetic    : пересборка только из кеша raw_merged (без сети)
        # incremental  : кеш + частичный сетевой запрос (догрузка хвоста)
        request_type = 'full'
        tail_fetch_attempted = False
        tail_fetch_success = None

        # Определяем координаты: если используются ручные координаты, то берем их,
        # иначе извлекаем координаты из зоны 'home'.
        if self._manual_coordinates and self._manual_latitude is not None and self._manual_longitude is not None:
            latitude = self._manual_latitude
            longitude = self._manual_longitude
        else:
            zone = self.hass.states.get("zone.home")
            if zone is None:
                raise UpdateFailed("Зона 'home' не найдена")
            latitude = zone.attributes.get("latitude")
            longitude = zone.attributes.get("longitude")

        index_url = self._build_index_url(latitude, longitude)

        data = {}

        try:
            async with aiohttp.ClientSession() as session:
                # --- Шаг 3: SMART-выбор датасета (один раз на старте/первом обновлении) ---
                await self._apply_smart_selection_if_needed(session, latitude, longitude)

                # --- runs catalog (диагностика свежести) ---
                _LOGGER.debug("%s Шаг 1: проверка свежести (runs catalog): %s", self._log_prefix, self._runs_catalog_url)
                run_id, run_start, run_end = await self._fetch_latest_run_info(session)
                self._latest_run_id = run_id
                self._latest_run_start = run_start
                self._latest_run_end = run_end
                _LOGGER.debug("%s Шаг 1: runs catalog результат: run_id=%s start=%s end=%s", self._log_prefix, run_id, run_start, run_end)

                # -----------------------------------------------------------------
                # Шаг 2: если run_id не изменился, пересобираем из кеша raw_merged
                # -----------------------------------------------------------------
                use_incremental = False
                if (
                    self._forecast_enabled
                    and run_id
                    and self._active_run_id == run_id
                    and isinstance(self.merged_data, dict)
                    and isinstance(self.merged_data.get("raw_merged"), dict)
                ):
                    raw_all = self.merged_data.get("raw_merged") or {}

                    # «Сдвигаем окно» по текущему времени:
                    # - чуть захватываем прошлое (1 час), чтобы не ломать текущую семантику "now"
                    # - конец окна = now + forecast_duration
                    now_utc = datetime.now(timezone.utc)
                    window_start = now_utc - timedelta(hours=1)
                    window_end = now_utc + timedelta(hours=self._forecast_duration)

                    # -----------------------------------------------------------------
                    # Шаг 2b: догрузка «хвоста» (опционально)
                    #
                    # Если окно прогноза уехало дальше, чем максимальная дата в кеше,
                    # подкачиваем только недостающий диапазон (time_start + time_duration)
                    # и дописываем точки в raw_all.
                    #
                    # Важно: хвост опционален — при ошибке не валим обновление.
                    # -----------------------------------------------------------------
                    try:
                        # Находим максимальное время в кеше
                        max_dt = None
                        for dt_s in raw_all.keys():
                            dt = self._parse_dt_utc(dt_s)
                            if dt is None:
                                continue
                            if (max_dt is None) or (dt > max_dt):
                                max_dt = dt

                        # Если кеш не дотягивает до конца окна — догружаем
                        # (порог 30 минут, чтобы не дёргаться из-за погрешностей)
                        if max_dt and (max_dt < (window_end - timedelta(minutes=30))):
                            tail_start_dt = max_dt + timedelta(hours=1)

                            # Если после +1ч старт уже за пределами окна — хвост не нужен
                            delta_sec = (window_end - tail_start_dt).total_seconds()
                            if delta_sec <= 0:
                                tail_start_dt = None
                            else:
                                missing_hours = math.ceil(delta_sec / 3600.0)
                                missing_hours = max(1, min(missing_hours, self._forecast_duration))

                                tail_time_start = tail_start_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
                                tail_time_duration = f"PT{missing_hours}H"

                            if tail_start_dt is None:
                                _LOGGER.debug(
                                    "%s Шаг 2b: хвост не нужен (tail_start уже за окном): max_dt=%s window_end=%s",
                                    self._log_prefix,
                                    max_dt,
                                    window_end,
                                )
                            else:
                                _LOGGER.debug(
                                    "%s Шаг 2b: догружаем хвост кеша: start=%s, duration=%s (missing_hours=%s)",
                                    self._log_prefix,
                                    tail_time_start,
                                    tail_time_duration,
                                    missing_hours,
                                )

                                # --- tail: index ---
                                tail_index_params = [
                                    "var=POLI",
                                    "var=POLISRC",
                                    "var=temp_2m",
                                    f"latitude={latitude}",
                                    f"longitude={longitude}",
                                    f"time_start={tail_time_start}",
                                    f"time_duration={tail_time_duration}",
                                    "accept=xml",
                                ]
                                tail_index_url = self._base_url + "?" + "&".join(tail_index_params)

                                # --- Диагностика: инкрементальный сетевой запрос хвоста ---
                                tail_fetch_attempted = True
                                _LOGGER.debug("%s Шаг 2b: tail index URL: %s", self._log_prefix, tail_index_url)

                                tail_index_xml = None
                                async with session.get(tail_index_url) as resp:
                                    _LOGGER.debug("%s Шаг 2b: tail index HTTP %s", self._log_prefix, resp.status)
                                    if resp.status == 200:
                                        async with async_timeout.timeout(10):
                                            tail_index_text = await resp.text()
                                        tail_index_xml = ET.fromstring(tail_index_text)
                                        tail_fetch_success = True

                                if tail_fetch_attempted and tail_fetch_success is None:
                                    # Запрос хвоста был, но HTTP!=200 или парсинг не удался
                                    tail_fetch_success = False

                                # --- tail: main (только если есть аллергены) ---
                                tail_main_xml = None
                                if self._var_list:
                                    tail_main_params = []
                                    for allergen in self._var_list:
                                        full_allergen = self._resolve_main_var_name(allergen)
                                        tail_main_params.append(f"var={full_allergen}")

                                    tail_main_params += [
                                        f"latitude={latitude}",
                                        f"longitude={longitude}",
                                        f"time_start={tail_time_start}",
                                        f"time_duration={tail_time_duration}",
                                        f"vertCoord={self._desired_altitude}",
                                        "accept=xml",
                                    ]
                                    tail_main_url = self._base_url + "?" + "&".join(tail_main_params)

                                    _LOGGER.debug("%s Шаг 2b: tail main URL: %s", self._log_prefix, tail_main_url)

                                    async with session.get(tail_main_url) as resp:
                                        _LOGGER.debug("%s Шаг 2b: tail main HTTP %s", self._log_prefix, resp.status)
                                        if resp.status == 200:
                                            async with async_timeout.timeout(10):
                                                tail_main_text = await resp.text()
                                            tail_main_xml = ET.fromstring(tail_main_text)

                                # Если tail index получили — выжимаем raw_merged и добавляем в кеш
                                if tail_index_xml is not None:
                                    from .data_processing import merge_station_features

                                    tail_merged = merge_station_features(
                                        tail_index_xml,
                                        tail_main_xml,
                                        hass=self.hass,
                                        base_url=self._base_url,
                                        forecast_enabled=True,
                                        selected_allergens=self._var_list,
                                        forecast_duration=self._forecast_duration,
                                    )
                                    tail_raw = tail_merged.get("raw_merged") or {}
                                    if tail_raw:
                                        raw_all.update(tail_raw)
                                        _LOGGER.debug("%s Шаг 2b: добавлено точек в кеш: %s", self._log_prefix, len(tail_raw))
                    except Exception as err:
                        _LOGGER.debug("%s Шаг 2b: ошибка догрузки хвоста (пропускаем): %s", self._log_prefix, err)

                        if tail_fetch_attempted and tail_fetch_success is None:
                            tail_fetch_success = False

                    raw_view = {}
                    for k, v in raw_all.items():
                        dt = self._parse_dt_utc(k)
                        if dt is None:
                            continue
                        if window_start <= dt <= window_end:
                            raw_view[k] = v

                    if raw_view:
                        # Если хвост не догружали — это чисто синтетическая пересборка из кеша.
                        # Если хвост догружали — это инкрементальный режим (кеш + частичный сетевой фетч).
                        request_type = 'incremental' if tail_fetch_attempted else 'synthetic'

                        _LOGGER.debug(
                            "%s Шаг 2: %s режим (run_id=%s). Пересобираем из кеша %s/%s точек.",
                            self._log_prefix,
                            request_type,
                            run_id,
                            len(raw_view),
                            len(raw_all),
                        )
                        data["index"] = self._build_station_features_xml_from_raw_merged(raw_view)
                        # На шаге 2 main не запрашиваем: мы пересобираем всё из кеша как «единый» индекс XML.
                        # Догрузка хвоста/доп.точек будет на следующем шаге.
                        # (Начиная с шага 2b хвост может догружаться прямо здесь, если окно прогноза уехало дальше кеша.)
                        use_incremental = True

                # Если инкрементальный режим не сработал — выполняем текущую (старую) логику запросов
                if not use_incremental:
                    # Запрос для index
                    _LOGGER.debug("%s Вызов API для index: %s", self._log_prefix, index_url)
                    async with session.get(index_url) as response:
                        _LOGGER.debug("%s Ответ для index с кодом %s", self._log_prefix, response.status)
                        if response.status != 200:
                            raise UpdateFailed(f"HTTP error (index): {response.status}")
                        async with async_timeout.timeout(10):
                            text = await response.text()
                            _LOGGER.debug("%s Получен ответ для index: %s", self._log_prefix, text[:200])
                            data["index"] = ET.fromstring(text)

                    # Если var_list задан, выполняем запрос для main
                    if self._var_list:
                        main_url = self._build_main_url(latitude, longitude)
                        _LOGGER.debug("%s Вызов API для main: %s", self._log_prefix, main_url)
                        async with session.get(main_url) as response:
                            _LOGGER.debug("%s Ответ для main с кодом %s", self._log_prefix, response.status)
                            if response.status != 200:
                                raise UpdateFailed(f"HTTP error (main): {response.status}")
                            async with async_timeout.timeout(10):
                                text = await response.text()
                                _LOGGER.debug("%s Получен ответ для main: %s", self._log_prefix, text[:200])
                                data["main"] = ET.fromstring(text)

                    # --- Шаг 2: фиксируем, на каком run_id построен актуальный кеш ---
                    # Обновляем только после успешного «полного» фетча (чтобы не закрепить битый/частичный результат).
                    if run_id:
                        self._active_run_id = run_id

        except Exception as err:
            raise UpdateFailed(f"Ошибка при получении или обработке XML: {err}")

        # Объединяем данные один раз и кешируем в merged_data,
        # при этом оригинальный словарь data возвращается как есть для совместимости
        try:
            from .data_processing import merge_station_features

            merged = merge_station_features(
                data.get("index"),
                data.get("main"),
                hass=self.hass,
                base_url=self._base_url,
                forecast_enabled=self._forecast_enabled,
                selected_allergens=self._var_list,
                forecast_duration=self._forecast_duration,
            )
            # Засекаем конец и вычисляем длительность фетча
            duration = time.monotonic() - start
            merged["last_fetch_duration"] = round(duration, 3)

            # --- runs catalog (диагностика) ---
            merged["runs_catalog_url"] = self._runs_catalog_url
            merged["latest_run_id"] = self._latest_run_id
            merged["latest_run_start"] = self._latest_run_start
            merged["latest_run_end"] = self._latest_run_end

            # --- Диагностика типа запроса (для SilamPollenFetchDurationSensor) ---
            merged["request_type"] = request_type
            merged["tail_fetch_attempted"] = tail_fetch_attempted
            merged["tail_fetch_success"] = tail_fetch_success

            # --- Runtime effective dataset info (для OptionsFlow/diagnostics) ---
            merged["dataset_selection"] = self._dataset_selection
            merged["effective_base_url"] = self._base_url

            _LOGGER.debug(
                "%s Сформированные объединённые данные (fetch duration: %.3fs): %s",
                self._log_prefix,
                duration,
                merged,
            )
            self.merged_data = {**merged}
        except Exception as err:
            _LOGGER.error("%s Ошибка при объединении или обработке прогнозных данных: %s", self._log_prefix, err)
            self.merged_data = {}
