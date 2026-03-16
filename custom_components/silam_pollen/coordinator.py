# coordinator.py

"""
Реализует SilamCoordinator для интеграции SILAM Pollen.
Использует DataUpdateCoordinator для обновления данных для всех сенсоров интеграции.

Шаг 1 (аккуратное внедрение):
- Добавлена лёгкая проверка "свежести" через THREDDS runs/catalog.xml (RunsCatalogManager).
- Данные каталога сохраняются в merged_data для диагностики.

Шаг 2 (аккуратное внедрение, без лишних изменений):
- Добавлен «инкрементальный» режим: если новый набор данных НЕ появился (run_id не изменился),
  то мы НЕ делаем полный запрос index/main, а пересобираем результат из уже сохранённого raw_merged.
- Шаг 2b (очень аккуратно): добавлена опциональная догрузка «хвоста» в инкрементальном режиме,
  если окно прогноза уехало дальше, чем максимальная дата в кеше.

Шаг 3 (SMART управление датасетом, только выбор источника — без догрузки):
- На старте SMART выбирается preferred-датасет по координатам (лёгкий NCSS probe).
- При деградации текущего датасета (catalog horizon < now + SMART_MIN_COVERAGE_HOURS)
  выполняется переоценка и переключение на fallback (через _set_base_url).
- При восстановлении preferred (по каталогу + подтверждение probe) выполняется возврат.
- В merged_data сохраняются effective_base_url и preferred_base_url для UI/диагностики.
"""

import math

import logging
import asyncio
import re
import time
import aiohttp
import async_timeout
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN,
    RUNS_CATALOG_MANAGER,
    URL_VAR_MAPPING,
    resolve_silam_var_name,
    DATASET_SRC_KEYS,
    SMART_MIN_COVERAGE_HOURS,
    SMART_NCSS_FAIL_STREAK_SWITCH,
)  # Импортируем константы и маппинг


_LOGGER = logging.getLogger(__name__)

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
        # Текущий preferred для координат (для UI/диагностики). Обновляется при SMART-probe/возврате.
        self._preferred_base_url = None
        # --- SMART: контроль проверок preferred на fallback ---
        # Чтобы не проверять восстановление каждый апдейт:
        # проверяем только если в preferred catalog появился новый run_id.
        self._preferred_last_seen_run_id: str | None = None
        self._preferred_last_checked_run_id: str | None = None

        self._forecast_enabled = forecast
        self._forecast_duration = forecast_duration

        # --- THREDDS runs catalog (проверка свежести) ---
        self._runs_catalog_url = self._derive_runs_catalog_url()
        self._latest_run_id = None
        self._latest_run_start = None
        self._latest_run_end = None

        # Общий менеджер runs catalog (domain-level) из hass.data[DOMAIN]
        self._runs_manager = hass.data.get(DOMAIN, {}).get(RUNS_CATALOG_MANAGER)

        # --- Шаг 2: «активный» run_id, на котором построен текущий кеш raw_merged ---
        # Нужен, чтобы понимать: «набор данных тот же» -> можно пересобрать из кеша без полного запроса.
        self._active_run_id = None
        # подряд ошибки NCSS при появлении нового run_id (SMART) ---
        # Используем _active_run_id как базу сравнения: если в каталоге новый run_id,
        # но NCSS временно падает — первый раз не переключаемся, копим streak.
        self._smart_ncss_fail_streak = 0
        # --- Шаг 4 (SMART): кеш гео-покрытия кандидатов по координатам ---
        # base_url -> True/False (True = NCSS probe подтвердил, False = детерминированно "не покрывает")
        self._smart_coord_ok: dict[str, bool] = {}

        # Извлекаем версию SILAM из BASE_URL
        match = re.search(r"pollen_v(\d+_\d+(?:_\d+)?)", self._base_url)
        if match:
            self.silam_version = match.group(1)
        else:
            self.silam_version = "unknown"

        # Инициализируем merged_data (будет заполняться после обновления)
        self.merged_data = {}
        # --- Источники данных по временным точкам (для SMART-склейки) ---
        # Ключи задаём через const.DATASET_SRC_KEYS (без URL, только имя датасета).
        # reverse: 'sep61' -> 'silam_europe_pollen_v6_1'
        self._src_reverse = {v: k for k, v in DATASET_SRC_KEYS.items()}


        super().__init__(
            hass,
            _LOGGER,
            name=f"SILAM Pollen Coordinator ({base_device_name})",
            update_interval=timedelta(minutes=update_interval),
            always_update=True,
        )

    # ---------------------------------------------------------------------
    # Lightweight profiling helpers (DEBUG-only)
    # ---------------------------------------------------------------------
    def _prof_start(self) -> float:
        """Start profiling timer (monotonic)."""
        return time.monotonic()

    def _prof(self, t0: float, label: str) -> None:
        """Log elapsed time since t0 (DEBUG-only)."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s PROF: %s: %.3fs",
                self._log_prefix,
                label,
                time.monotonic() - t0,
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

    def _derive_runs_catalog_url_for_base_url(self, base_url: str | None) -> str | None:
        """Строит URL runs/catalog.xml по произвольному base_url (NCSS grid)."""
        if not base_url:
            return None
        try:
            u = urlparse(base_url)
            parts = [p for p in u.path.split("/") if p]
            grid_idx = parts.index("grid")
            dataset = parts[grid_idx + 1]
            return f"{u.scheme}://{u.netloc}/thredds/catalog/{dataset}/runs/catalog.xml"
        except Exception:
            return None

    async def _fetch_latest_run_info(self, session):
        """Возвращает (run_id, start, end) из runs/catalog.xml.

        Теперь источник только один: общий RunsCatalogManager (кэш + дедуп).
        """
        if not self._runs_catalog_url:
            return None, None, None

        if self._runs_manager is None:
            _LOGGER.debug(
                "%s runs catalog: RunsCatalogManager не инициализирован (url=%s)",
                self._log_prefix,
                self._runs_catalog_url,
            )
            return None, None, None

        try:
            latest = await self._runs_manager.async_get_latest(self._runs_catalog_url)
            if latest and latest.run_id:
                _LOGGER.debug(
                    "%s Шаг 1: runs catalog (manager): run=%s start=%s end=%s",
                    self._log_prefix,
                    latest.run_id,
                    latest.start,
                    latest.end,
                )
                return latest.run_id, latest.start, latest.end

            _LOGGER.debug(
                "%s Шаг 1: runs catalog (manager): нет latest run (url=%s)",
                self._log_prefix,
                self._runs_catalog_url,
            )
            return None, None, None

        except Exception as err:
            _LOGGER.debug(
                "%s Шаг 1: runs catalog (manager) ошибка (%s): %s",
                self._log_prefix,
                self._runs_catalog_url,
                err,
            )
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

        _LOGGER.debug("%s SMART: base_url switched: %s -> %s", self._log_prefix, old, new_base_url)

    async def _smart_select_base_url(
        self,
        session,
        latitude,
        longitude,
        *,
        require_catalog_coverage: bool,
    ) -> str | None:
        """Единый SMART-селектор (общая логика).

        - require_catalog_coverage=True:
            кандидат должен покрывать now+SMART_MIN_COVERAGE_HOURS по runs/catalog.xml,
            и пройти лёгкий NCSS-probe (PT0H).
        - require_catalog_coverage=False:
            только лёгкий NCSS-probe (PT0H) для определения preferred по координатам.
        """
        candidates = self._smart_candidates or [self._base_url]

        now_utc = datetime.now(timezone.utc)
        min_end_dt = now_utc + timedelta(hours=SMART_MIN_COVERAGE_HOURS)

        for url in candidates:
            if not url:
                continue

            # --- SMART candidate gate: проверяем, что runs/catalog.xml у кандидата покрывает now+SMART_MIN_COVERAGE_HOURS ---
            if require_catalog_coverage and self._runs_manager is not None:
                try:
                    # Собираем runs/catalog.xml для base_url кандидата
                    u = urlparse(url)
                    parts = [p for p in u.path.split("/") if p]

                    # Ожидаем путь вида: .../thredds/ncss/grid/<dataset>/<file>
                    grid_idx = parts.index("grid")
                    dataset = parts[grid_idx + 1]

                    candidate_catalog_url = (
                        f"{u.scheme}://{u.netloc}/thredds/catalog/{dataset}/runs/catalog.xml"
                    )

                    latest = await self._runs_manager.async_get_latest(candidate_catalog_url)
                    end_dt = self._parse_dt_utc(latest.end) if latest else None

                    # Если нет end_dt или покрытие меньше порога — кандидат не подходит
                    if not end_dt or end_dt < min_end_dt:
                        _LOGGER.debug(
                            "%s SMART probe skip %s: catalog_end=%s < min_end=%s",
                            self._log_prefix,
                            url,
                            end_dt,
                            min_end_dt,
                        )
                        continue

                except Exception as err:
                    # Любая проблема с разбором URL/каталога — просто пропускаем кандидата
                    _LOGGER.debug(
                        "%s SMART catalog check failed for %s: %s",
                        self._log_prefix,
                        url,
                        err,
                    )
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
                            txt = await resp.text()
                            if txt and txt.strip():
                                try:
                                    ET.fromstring(txt)
                                    return url
                                except ET.ParseError:
                                    _LOGGER.debug(
                                        "%s SMART probe skip %s: HTTP 200 but invalid XML",
                                        self._log_prefix, url,
                                    )
                            else:
                                _LOGGER.debug(
                                    "%s SMART probe skip %s: HTTP 200 but empty response",
                                    self._log_prefix, url,
                                )
            except Exception as err:
                _LOGGER.debug("%s SMART probe failed for %s: %s", self._log_prefix, url, err)

        return None

    async def _smart_probe_best_base_url(self, session, latitude, longitude) -> str | None:
        """Fallback-селектор: кандидат должен пройти gate по каталогу + probe по координатам."""
        return await self._smart_select_base_url(
            session, latitude, longitude, require_catalog_coverage=True
        )

    async def _smart_get_preferred_base_url(self, session, latitude, longitude) -> str | None:
        """Preferred base_url для текущих координат.

        Preferred = первый кандидат из self._smart_candidates,
        который проходит лёгкий NCSS-probe (PT0H).
        """
        return await self._smart_select_base_url(
            session, latitude, longitude, require_catalog_coverage=False
        )

    async def _smart_probe_coord_coverage(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        latitude: float,
        longitude: float,
    ) -> bool:
        """Лёгкий probe: покрывает ли датасет координаты (без привязки к forecast).

        Важно:
        - сетевые/временные ошибки НЕ считаем "False" (не кэшируем как непокрытие)
        - детерминированные ответы (200 + валидный XML) => True
        - HTTP 400/404 (часто "point outside grid") => False
        """
        # Если уже знаем — возвращаем сразу
        if base_url in self._smart_coord_ok:
            return self._smart_coord_ok[base_url]

        # Минимальный index probe на PT0H (как в SMART)
        probe_params = [
            "var=POLI",
            "var=POLISRC",
            "var=temp_2m",
            f"latitude={latitude}",
            f"longitude={longitude}",
            "time_start=present",
            "time_duration=PT0H",
            "accept=xml",
        ]
        probe_url = base_url + "?" + "&".join(probe_params)

        try:
            async with session.get(probe_url) as resp:
                st = resp.status

                # Детерминированное "нет покрытия" (обычно координата вне области)
                if st in (400, 404):
                    self._smart_coord_ok[base_url] = False
                    return False

                if st != 200:
                    # временная проблема (5xx/429/etc) — не кэшируем
                    return True

                async with async_timeout.timeout(10):
                    txt = await resp.text()

                # HTTP 200 but empty/whitespace-only body means the
                # coordinates fall outside the dataset's spatial grid.
                if not txt or not txt.strip():
                    _LOGGER.debug(
                        "%s SMART coord probe: HTTP 200 but empty response for %s",
                        self._log_prefix, base_url,
                    )
                    self._smart_coord_ok[base_url] = False
                    return False

                # Пробуем распарсить XML, если получилось — это покрытие
                try:
                    ET.fromstring(txt)
                except ET.ParseError:
                    _LOGGER.debug(
                        "%s SMART coord probe: HTTP 200 but invalid XML for %s",
                        self._log_prefix, base_url,
                    )
                    self._smart_coord_ok[base_url] = False
                    return False

                self._smart_coord_ok[base_url] = True
                return True

        except Exception:
            # Любая сетевуха/таймаут — не делаем вывод "не покрывает"
            return True

    async def _apply_smart_selection_if_needed(self, session, latitude, longitude) -> None:
        """Применяет политику SMART: выбирает лучший датасет один раз на старте."""
        if self._dataset_selection != "smart":
            return
        if self._smart_probe_done:
            return

        self._smart_probe_done = True

        # На старте выбираем preferred по координатам (единая логика с UI/возвратом).
        chosen = await self._smart_get_preferred_base_url(session, latitude, longitude)
        self._preferred_base_url = chosen
        if chosen and chosen != self._base_url:
            self._set_base_url(chosen)
        # preferred мог измениться — сбросим маркер проверенного run_id
        self._preferred_last_checked_run_id = None

        # Пишем минимальную диагностическую инфу (дальше можно вывести в diagnostics сенсор)
        try:
            if isinstance(self.merged_data, dict):
                self.merged_data["dataset_selection"] = self._dataset_selection
                self.merged_data["effective_base_url"] = self._base_url
        except Exception:
            pass

    async def _smart_handle_ncss_http_error(
        self,
        *,
        kind: str,
        status: int,
        session,
        latitude: float,
        longitude: float,
        run_id: str | None,
        run_start: str | None,
        run_end: str | None,
        expect_new_run_fetch: bool,
    ) -> None:
        """Шаг 1 (SMART): обработка HTTP!=200 на NCSS (index/main) при появлении нового run_id.

        Поведение:
        - Если не expect_new_run_fetch -> просто UpdateFailed (как раньше).
        - Если expect_new_run_fetch -> копим streak, 1-я ошибка без перевыбора,
        при достижении порога делаем SMART-switch через _set_base_url(), затем всё равно UpdateFailed
        (чтобы сохранить старые данные и повторить на следующем цикле).
        """
        if not expect_new_run_fetch:
            raise UpdateFailed(f"HTTP error ({kind}): {status}")

        self._smart_ncss_fail_streak += 1
        _LOGGER.debug(
            "%s SMART: NCSS %s HTTP=%s на новом run_id=%s (active=%s), streak=%s/%s. "
            "Перевыбор датасета пропускаем до порога.",
            self._log_prefix,
            kind,
            status,
            run_id,
            self._active_run_id,
            self._smart_ncss_fail_streak,
            SMART_NCSS_FAIL_STREAK_SWITCH,
        )

        # До порога — не переключаемся
        if self._smart_ncss_fail_streak < SMART_NCSS_FAIL_STREAK_SWITCH:
            raise UpdateFailed(f"HTTP error ({kind}): {status}")

        # Достигли порога — пробуем выбрать рабочий датасет
        chosen = await self._smart_probe_best_base_url(session, latitude, longitude)
        if chosen and chosen != self._base_url:
            self._set_base_url(chosen)

            _LOGGER.debug(
                "%s Шаг 1: runs catalog после SMART-switch (NCSS errors): %s",
                self._log_prefix,
                self._runs_catalog_url,
            )

            # Обновим информацию о run для нового base_url (чтобы диагностика не вела в заблуждение)
            new_run_id, new_run_start, new_run_end = await self._fetch_latest_run_info(session)
            self._latest_run_id = new_run_id
            self._latest_run_start = new_run_start
            self._latest_run_end = new_run_end

        # Сбрасываем streak, чтобы следующий цикл начал "с чистого листа"
        self._smart_ncss_fail_streak = 0

        # На этом цикле всё равно оставляем старые данные (UpdateFailed),
        # а уже следующий апдейт отработает на новом base_url (если переключились).
        raise UpdateFailed(f"HTTP error ({kind}): {status}")

    # ---------------------------------------------------------------------
    # Шаг 2: вспомогательные функции для «инкрементального» режима
    # ---------------------------------------------------------------------
    def _catalog_allows_tail(
        self,
        *,
        cache_max_dt: datetime | None,
        window_end: datetime,
    ) -> bool:
        """
        Возвращает True, если в runs/catalog.xml есть данные,
        которые можно догрузить после cache_max_dt.
        """
        catalog_end_dt = self._parse_dt_utc(self._latest_run_end)
        if not catalog_end_dt:
            # Нет информации из каталога — ведём себя как раньше
            return True

        # В каталоге данных дальше кеша нет
        if cache_max_dt and cache_max_dt >= catalog_end_dt:
            _LOGGER.debug(
                "%s Шаг 2b: хвост запрещён каталогом "
                "(cache_max=%s, catalog_end=%s)",
                self._log_prefix,
                cache_max_dt,
                catalog_end_dt,
            )
            return False

        # Даже с учётом окна догружать нечего
        wanted_end = min(window_end, catalog_end_dt)
        if cache_max_dt and cache_max_dt >= wanted_end:
            _LOGGER.debug(
                "%s Шаг 2b: хвост не нужен (кеш покрывает окно каталога) "
                "(cache_max=%s, wanted_end=%s)",
                self._log_prefix,
                cache_max_dt,
                wanted_end,
            )
            return False

        return True

    async def _fetch_raw_range_from_base_url(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        latitude: float,
        longitude: float,
        time_start: str,
        time_duration: str,
        src_key: str,
    ) -> dict:
        """Загружает диапазон (index + main) и возвращает raw_merged (с проставленным src_key)."""

        # --- index ---
        index_params = [
            "var=POLI",
            "var=POLISRC",
            "var=temp_2m",
            f"latitude={latitude}",
            f"longitude={longitude}",
            f"time_start={time_start}",
            f"time_duration={time_duration}",
            "accept=xml",
        ]
        index_url = base_url + "?" + "&".join(index_params)

        index_xml = None
        async with session.get(index_url) as resp:
            if resp.status != 200:
                return {}
            async with async_timeout.timeout(10):
                t = await resp.text()
            index_xml = ET.fromstring(t)

        # --- main (если есть аллергены) ---
        main_xml = None
        if self._var_list:
            main_params = []
            for allergen in self._var_list:
                full_allergen = resolve_silam_var_name(allergen)
                main_params.append(f"var={full_allergen}")

            main_params += [
                f"latitude={latitude}",
                f"longitude={longitude}",
                f"time_start={time_start}",
                f"time_duration={time_duration}",
                f"vertCoord={self._desired_altitude}",
                "accept=xml",
            ]
            main_url = base_url + "?" + "&".join(main_params)

            async with session.get(main_url) as resp:
                if resp.status != 200:
                    return {}
                async with async_timeout.timeout(10):
                    t = await resp.text()
                main_xml = ET.fromstring(t)

        from .data_processing import merge_station_features

        merged = merge_station_features(
            index_xml,
            main_xml,
            hass=self.hass,
            base_url=base_url,
            forecast_enabled=True,
            selected_allergens=self._var_list,
            forecast_duration=self._forecast_duration,
        )
        raw = merged.get("raw_merged") or {}
        if raw:
            self._apply_src_to_raw(raw, src_key)
        return raw

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

    def _normalize_dt_key_to_z(self, dt_key: str) -> str:
        """Приводит любую ISO-строку к каноническому ключу UTC в формате ...Z."""
        dt = self._parse_dt_utc(dt_key)
        if dt is None:
            return dt_key
        dt = dt.astimezone(timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    def _dataset_name_from_base_url(self, base_url: str | None) -> str:
        """Возвращает имя датасета из NCSS grid base_url (без URL-частей)."""
        if not base_url:
            return "-"
        try:
            u = urlparse(base_url)
            parts = [p for p in (u.path or "").split("/") if p]
            # ... /thredds/ncss/grid/<dataset>/<file>.ncd
            if "grid" in parts:
                gi = parts.index("grid")
                if gi + 1 < len(parts):
                    return parts[gi + 1]
            return "-"
        except Exception:
            return "-"

    def _src_key_for_dataset(self, dataset_name: str) -> str:
        """Короткий ключ источника: берём из DATASET_SRC_KEYS, иначе используем само имя датасета."""
        if not dataset_name or dataset_name == "-":
            return "-"
        return DATASET_SRC_KEYS.get(dataset_name, dataset_name)

    def _apply_src_to_raw(self, raw: dict | None, src_key: str) -> None:
        """Проставляет src_key в каждом таймслоте raw_merged как payload['s']."""
        if not isinstance(raw, dict):
            return
        for _, payload in raw.items():
            if isinstance(payload, dict):
                payload.setdefault("s", src_key)

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

        # --- PROF: общий таймер для точечных меток ---
        t0 = self._prof_start()
        self._prof(t0, "start")

        # даём циклу событий шанс выполнить ожидающие callback'и
        await asyncio.sleep(0)
        self._prof(t0, "after_yield_0")

        # --- Диагностика типа запроса (для SilamPollenFetchDurationSensor) ---
        # full         : обычный полный сетевой фетч index/main
        # synthetic    : пересборка только из кеша raw_merged (без сети)
        # incremental  : кеш + частичный сетевой запрос (догрузка хвоста)
        request_type = 'full'
        tail_fetch_attempted = False
        tail_fetch_network = False
        tail_fetch_success = None

        raw_view = None  # используется для восстановления меток источника 's' при инкрементальной пересборке
        raw_all_ref = None  # ссылка на кеш raw_merged, если работали в incremental/synthetic ветке

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

        # index_url строим заранее, но после SMART-переключений его пересчитаем (см. ниже)
        index_url = self._build_index_url(latitude, longitude)

        data = {}

        try:
            async with aiohttp.ClientSession() as session:
                # --- Шаг 3: SMART-выбор датасета (один раз на старте/первом обновлении) ---
                await self._apply_smart_selection_if_needed(session, latitude, longitude)

                # После SMART выбора на старте пересчитываем index_url (base_url мог измениться)
                index_url = self._build_index_url(latitude, longitude)

                # --- runs catalog (диагностика свежести) ---
                self._prof(t0, "before_step1_runs_catalog")
                _LOGGER.debug("%s Шаг 1: проверка свежести (runs catalog): %s", self._log_prefix, self._runs_catalog_url)
                run_id, run_start, run_end = await self._fetch_latest_run_info(session)
                self._latest_run_id = run_id
                self._latest_run_start = run_start
                self._latest_run_end = run_end
                self._prof(t0, "after_step1_runs_catalog")
                _LOGGER.debug("%s Шаг 1: runs catalog результат: run_id=%s start=%s end=%s", self._log_prefix, run_id, run_start, run_end)

                # -----------------------------------------------------------------
                # Шаг 3: SMART управление датасетом
                #
                # Логика:
                # 1) Если текущий датасет не покрывает now + SMART_MIN_COVERAGE_HOURS
                #    → переоценка и переход на fallback
                # 2) ИНАЧЕ, если мы на fallback и preferred восстановился
                #    → возврат на preferred
                # -----------------------------------------------------------------
                if self._dataset_selection == "smart":
                    now_utc = datetime.now(timezone.utc)
                    threshold_dt = now_utc + timedelta(hours=SMART_MIN_COVERAGE_HOURS)

                    catalog_end_dt = self._parse_dt_utc(run_end)
                    no_data = (
                        run_id is None
                        or (catalog_end_dt is not None and catalog_end_dt < threshold_dt)
                    )

                    # -------------------------------------------------------------
                    # 1) Деградация: текущий датасет не покрывает окно
                    # -------------------------------------------------------------
                    if no_data:
                        _LOGGER.debug(
                            "%s SMART: текущий датасет не покрывает окно "
                            "(run_id=%s, end=%s < threshold=%s). Переоценка...",
                            self._log_prefix,
                            run_id,
                            run_end,
                            threshold_dt,
                        )

                        chosen = await self._smart_probe_best_base_url(
                            session, latitude, longitude
                        )
                        if chosen and chosen != self._base_url:
                            self._set_base_url(chosen)

                            # После SMART-switch пересчитываем index_url (base_url изменился)
                            index_url = self._build_index_url(latitude, longitude)

                            # Обновляем runs catalog после переключения
                            _LOGGER.debug(
                                "%s Шаг 1: runs catalog после SMART-switch: %s",
                                self._log_prefix,
                                self._runs_catalog_url,
                            )
                            run_id, run_start, run_end = await self._fetch_latest_run_info(session)
                            self._latest_run_id = run_id
                            self._latest_run_start = run_start
                            self._latest_run_end = run_end

                    # -------------------------------------------------------------
                    # 2) Восстановление: возврат на preferred (только на fallback и только при новом run_id в каталоге preferred)
                    # -------------------------------------------------------------
                    elif self._smart_candidates:
                        preferred = self._preferred_base_url

                        # Если preferred ещё не определён (редко: например, старый объект/миграция),
                        # определяем один раз (может быть сетевой probe) — но только если мы вообще в SMART.
                        if not preferred:
                            preferred = await self._smart_get_preferred_base_url(session, latitude, longitude)
                            self._preferred_base_url = preferred

                        # Проверяем восстановление только если мы реально на fallback
                        if preferred and preferred != self._base_url and self._runs_manager is not None:
                            try:
                                preferred_catalog_url = self._derive_runs_catalog_url_for_base_url(preferred)
                                if preferred_catalog_url:
                                    latest_pref = await self._runs_manager.async_get_latest(preferred_catalog_url)

                                    pref_run_id = getattr(latest_pref, "run_id", None) if latest_pref else None
                                    pref_end = getattr(latest_pref, "end", None) if latest_pref else None

                                    # запоминаем “последний увиденный” run_id у preferred
                                    if pref_run_id:
                                        self._preferred_last_seen_run_id = pref_run_id

                                    # Ключевое правило: НИЧЕГО не делаем, пока run_id не изменился
                                    if not pref_run_id or pref_run_id == self._preferred_last_checked_run_id:
                                        # нет нового run_id — значит нет смысла проверять восстановление
                                        pass
                                    else:
                                        # появился новый run_id у preferred — теперь можно проверить восстановление один раз
                                        self._preferred_last_checked_run_id = pref_run_id

                                        pref_end_dt = self._parse_dt_utc(pref_end)
                                        if pref_end_dt and pref_end_dt >= threshold_dt:
                                            # опционально (и желательно): проверить, что preferred действительно покрывает координаты (кешируется)
                                            ok = await self._smart_probe_coord_coverage(session, preferred, latitude, longitude)
                                            if ok:
                                                _LOGGER.debug(
                                                    "%s SMART: preferred обновился (new run_id=%s) и покрывает окно "
                                                    "(end=%s >= threshold=%s). Возврат.",
                                                    self._log_prefix,
                                                    pref_run_id,
                                                    pref_end_dt,
                                                    threshold_dt,
                                                )

                                                self._set_base_url(preferred)

                                                # После возврата пересчитываем index_url (base_url изменился)
                                                index_url = self._build_index_url(latitude, longitude)

                                                # Обновляем runs catalog после возврата (для диагностики)
                                                _LOGGER.debug(
                                                    "%s Шаг 1: runs catalog после возврата на preferred: %s",
                                                    self._log_prefix,
                                                    self._runs_catalog_url,
                                                )
                                                run_id, run_start, run_end = await self._fetch_latest_run_info(session)
                                                self._latest_run_id = run_id
                                                self._latest_run_start = run_start
                                                self._latest_run_end = run_end

                            except Exception as err:
                                _LOGGER.debug("%s SMART: ошибка проверки preferred (%s)", self._log_prefix, err)

                # --- Источник данных (коротко) для SMART-склейки ---
                src_ds = self._dataset_name_from_base_url(self._base_url)
                src_key = self._src_key_for_dataset(src_ds)

                # PROF: после SMART-управления датасетом
                self._prof(t0, "after_smart_dataset_mgmt")
                # --- Шаг 1 (SMART): ожидаем обновление на новом run_id (без привязки к forecast) ---
                # Триггерим "мягкую" политику ошибок только если:
                # - SMART включён
                # - в каталоге уже новый run_id (run_id != _active_run_id)
                # - и каталог обещает окно хотя бы SMART_MIN_COVERAGE_HOURS вперёд
                expect_new_run_fetch = False
                if self._dataset_selection == "smart" and run_id and self._active_run_id and run_id != self._active_run_id:
                    now_utc = datetime.now(timezone.utc)
                    threshold_dt = now_utc + timedelta(hours=SMART_MIN_COVERAGE_HOURS)
                    catalog_end_dt = self._parse_dt_utc(run_end)
                    if catalog_end_dt is not None and catalog_end_dt >= threshold_dt:
                        expect_new_run_fetch = True

                # -----------------------------------------------------------------
                # Шаг 2: если run_id не изменился, пересобираем из кеша raw_merged
                # -----------------------------------------------------------------
                self._prof(t0, "before_incremental_if")
                use_incremental = False
                if (
                    self._forecast_enabled
                    and run_id
                    and self._active_run_id == run_id
                    and isinstance(self.merged_data, dict)
                    and isinstance(self.merged_data.get("raw_merged"), dict)
                ):
                    self._prof(t0, "entered_incremental_if")
                    raw_all = self.merged_data.get("raw_merged") or {}
                    raw_all_ref = raw_all  # важно: дальше Шаг 2b/Шаг 4 расширяют именно этот dict

                    # Проставляем источник для старых кешей, где меток ещё не было
                    self._apply_src_to_raw(raw_all, src_key)

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

                        # Если кеш не дотягивает до конца окна — потенциально догружаем
                        # НО сначала проверяем, разрешает ли это runs/catalog.xml
                        if (
                            max_dt
                            and (max_dt < (window_end - timedelta(minutes=30)))
                            and self._catalog_allows_tail(
                                cache_max_dt=max_dt,
                                window_end=window_end,
                            )
                        ):
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
                                tail_fetch_network = True
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
                                        full_allergen = resolve_silam_var_name(allergen)
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
                                        self._apply_src_to_raw(tail_raw, src_key)
                                        raw_all.update(tail_raw)
                                        _LOGGER.debug("%s Шаг 2b: добавлено точек в кеш: %s", self._log_prefix, len(tail_raw))
                        else:
                            tail_fetch_attempted = True
                            tail_fetch_success = False  # не ошибка, а осознанный skip
                            _LOGGER.debug(
                                "%s Шаг 2b: догрузка хвоста пропущена (каталог ограничивает окно)",
                                self._log_prefix,
                            )
                    except Exception as err:
                        _LOGGER.debug("%s Шаг 2b: ошибка догрузки хвоста (пропускаем): %s", self._log_prefix, err)

                        if tail_fetch_attempted and tail_fetch_success is None:
                            tail_fetch_success = False
                    ####
                    # -----------------------------------------------------------------
                    # Шаг 4 (SMART): дозаполнение missing-times из других датасетов
                    # Только если:
                    # - SMART режим
                    # - forecast включён (есть целевой горизонт)
                    # -----------------------------------------------------------------
                    if self._dataset_selection == "smart" and self._forecast_enabled:
                        try:
                            # 1) Собираем целевые слоты (почасовые) в окне window_start..window_end
                            # Используем UTC и ISO-ключи как в raw_merged
                            slots: list[str] = []
                            cur = window_start.replace(minute=0, second=0, microsecond=0)
                            end = window_end.replace(minute=0, second=0, microsecond=0)

                            # чуть аккуратнее: если window_start был "минус 1 час", мы всё равно строим слоты на весь горизонт
                            while cur <= end:
                                slots.append(cur.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
                                cur += timedelta(hours=1)

                            # Нормализованное множество "что уже есть" — только для сравнения.
                            # raw_all не трогаем (там пусть остаётся как пришло из XML, т.е. ...Z).
                            present_norm = {self._normalize_dt_key_to_z(k) for k in raw_all.keys()}

                            missing = [s for s in slots if s not in present_norm]

                            if missing:
                                _LOGGER.debug("%s Шаг 4: missing-times до дозаполнения: %s", self._log_prefix, len(missing))

                                # 2) Сегменты missing (непрерывные по часу)
                                missing_dts = []
                                for s in missing:
                                    dt = self._parse_dt_utc(s)
                                    if dt is not None:
                                        missing_dts.append(dt)
                                missing_dts.sort()

                                segments: list[tuple[datetime, datetime]] = []
                                seg_start = None
                                prev = None
                                for dt in missing_dts:
                                    if seg_start is None:
                                        seg_start = dt
                                        prev = dt
                                        continue
                                    if dt == prev + timedelta(hours=1):
                                        prev = dt
                                    else:
                                        segments.append((seg_start, prev))
                                        seg_start = dt
                                        prev = dt
                                if seg_start is not None and prev is not None:
                                    segments.append((seg_start, prev))

                                # 3) Для каждого сегмента ищем первый подходящий кандидат по приоритету
                                for seg_a, seg_b in segments:
                                    # берем длительность (в часах) включая край
                                    hours = int((seg_b - seg_a).total_seconds() // 3600) + 1
                                    if hours <= 0:
                                        continue

                                    seg_time_start = seg_a.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                                    seg_time_duration = f"PT{hours}H"

                                    filled = False

                                    for cand in (self._smart_candidates or []):
                                        if not cand or cand == self._base_url:
                                            continue

                                        # 3.1) (A) runs_catalog: должен пересекаться по времени
                                        cand_catalog_url = self._derive_runs_catalog_url_for_base_url(cand)
                                        if not cand_catalog_url or self._runs_manager is None:
                                            continue

                                        info = await self._runs_manager.async_get_latest(cand_catalog_url)
                                        if not info:
                                            continue

                                        cand_end = self._parse_dt_utc(getattr(info, "end", None))
                                        cand_start = self._parse_dt_utc(getattr(info, "start", None))
                                        if cand_end is None or cand_start is None:
                                            continue

                                        # если кандидат не покрывает сегмент по времени — пропускаем
                                        if cand_end < seg_a or cand_start > seg_b:
                                            continue

                                        # 3.2) (B) geo probe: покрывает ли координаты (лениво + кеш)
                                        ok = await self._smart_probe_coord_coverage(session, cand, latitude, longitude)
                                        if not ok:
                                            continue

                                        # 3.3) src_key для кандидата (если есть в справочнике — используем, иначе делаем fallback key)
                                        cand_ds = self._dataset_name_from_base_url(cand)
                                        cand_src = self._src_key_for_dataset(cand_ds)

                                        raw_seg = await self._fetch_raw_range_from_base_url(
                                            session=session,
                                            base_url=cand,
                                            latitude=latitude,
                                            longitude=longitude,
                                            time_start=seg_time_start,
                                            time_duration=seg_time_duration,
                                            src_key=cand_src,
                                        )

                                        if raw_seg:
                                            # 4) НЕ ПЕРЕТИРАЕМ primary: добавляем только отсутствующие ключи
                                            add_cnt = 0
                                            for k, v in raw_seg.items():
                                                nk = self._normalize_dt_key_to_z(k)

                                                # не создаём дубликат "Z vs +00:00": проверяем по нормализованному множеству
                                                if nk in present_norm:
                                                    continue

                                                raw_all[nk] = v
                                                present_norm.add(nk)
                                                add_cnt += 1

                                            _LOGGER.debug(
                                                "%s Шаг 4: сегмент %s..%s дозаполнен из кандидата (%s): +%s",
                                                self._log_prefix,
                                                seg_a,
                                                seg_b,
                                                cand_src,
                                                add_cnt,
                                            )
                                            filled = True
                                            break

                                    if not filled:
                                        _LOGGER.debug(
                                            "%s Шаг 4: не удалось дозаполнить сегмент %s..%s (нет подходящих кандидатов)",
                                            self._log_prefix,
                                            seg_a,
                                            seg_b,
                                        )

                        except Exception as err:
                            _LOGGER.debug("%s Шаг 4: ошибка SMART дозаполнения (пропускаем): %s", self._log_prefix, err)

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
                        request_type = 'incremental' if tail_fetch_network else 'synthetic'

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
                            await self._smart_handle_ncss_http_error(
                                kind="index",
                                status=response.status,
                                session=session,
                                latitude=latitude,
                                longitude=longitude,
                                run_id=run_id,
                                run_start=run_start,
                                run_end=run_end,
                                expect_new_run_fetch=expect_new_run_fetch,
                            )

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
                                await self._smart_handle_ncss_http_error(
                                    kind="main",
                                    status=response.status,
                                    session=session,
                                    latitude=latitude,
                                    longitude=longitude,
                                    run_id=run_id,
                                    run_start=run_start,
                                    run_end=run_end,
                                    expect_new_run_fetch=expect_new_run_fetch,
                                )

                            async with async_timeout.timeout(10):
                                text = await response.text()
                                _LOGGER.debug("%s Получен ответ для main: %s", self._log_prefix, text[:200])
                                data["main"] = ET.fromstring(text)

                    # --- Шаг 2: фиксируем, на каком run_id построен актуальный кеш ---
                    # Обновляем только после успешного «полного» фетча (чтобы не закрепить битый/частичный результат).
                    if run_id:
                        self._active_run_id = run_id
                        # Успешно обновились — сбрасываем streak ошибок NCSS
                        self._smart_ncss_fail_streak = 0

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
            # Если обновление шло через synthetic/incremental (кеш + опциональные догрузки),
            # то авторитетный raw_merged — это raw_all (который мы расширяли на шаге 2b/4).
            # Иначе merge_station_features может "потерять" добавленные точки при пересборке из index XML.
            if use_incremental and isinstance(raw_all_ref, dict):
                merged["raw_merged"] = raw_all_ref

            # --- Источник данных по временным точкам (для SMART-склейки) ---
            merged_raw = merged.get("raw_merged")
            if isinstance(merged_raw, dict):
                if raw_view:
                    # Инкрементальная пересборка: восстанавливаем 's' из raw_view по ключу datetime
                    for dt_s, payload in merged_raw.items():
                        if not isinstance(payload, dict):
                            continue
                        src_payload = raw_view.get(dt_s) if isinstance(raw_view, dict) else None
                        if isinstance(src_payload, dict) and "s" in src_payload:
                            payload["s"] = src_payload["s"]
                        else:
                            payload.setdefault("s", src_key)
                else:
                    # Полный фетч: весь merged_raw относится к текущему датасету
                    self._apply_src_to_raw(merged_raw, src_key)

                # Собираем только реально использованные источники в этом merged
                used_src: dict[str, str] = {}
                for payload in merged_raw.values():
                    if isinstance(payload, dict):
                        k = payload.get("s")
                        if not k:
                            continue
                        ds = self._src_reverse.get(k) if isinstance(self._src_reverse, dict) else None
                        # Если ключ не из справочника, считаем, что это уже имя датасета (fallback)
                        used_src[k] = ds or k
                merged["src"] = used_src
            else:
                merged["src"] = {src_key: src_ds}
            # Засекаем конец и вычисляем длительность фетча
            duration = time.monotonic() - start
            merged["last_fetch_duration"] = round(duration, 3)

            merged["diag"] = {
            # --- runs catalog (диагностика) ---
            "runs_catalog": {
                "url": self._runs_catalog_url,
                "latest_run_id": self._latest_run_id,
                "latest_run_start": self._latest_run_start,
                "latest_run_end": self._latest_run_end,
            },
            # --- Диагностика типа запроса (для SilamPollenFetchDurationSensor) ---
            "request": {
                "type": request_type,
                "tail_fetch_attempted": tail_fetch_attempted,
                "tail_fetch_network": tail_fetch_network,
                "tail_fetch_success": tail_fetch_success,
            },
            # --- Runtime effective dataset info (для OptionsFlow/diagnostics) ---
            "dataset": {
                "selection": self._dataset_selection,
                "effective_base_url": self._base_url,
                "preferred_base_url": self._preferred_base_url,
            },
            }

            _LOGGER.debug(
                "%s Сформированные объединённые данные (fetch duration: %.3fs): %s",
                self._log_prefix,
                duration,
                #merged,
                merged.get("diag"),
            )
            self.merged_data = {**merged}
        except Exception as err:
            _LOGGER.error("%s Ошибка при объединении или обработке прогнозных данных: %s", self._log_prefix, err)
            self.merged_data = {}
