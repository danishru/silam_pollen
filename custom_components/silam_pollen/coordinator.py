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

Шаг 5b (root catalog hard gate):
- Root catalog становится обязательной ранней online-проверкой перед SMART,
  runs/catalog.xml и NCSS fetch.
- Если root catalog недоступен или невалиден, сетевые запросы к runs/NCSS
  не выполняются: обычный refresh может восстановиться из кэша, а full_refresh
  завершается ошибкой без изменения persistent cache.
- Если текущий датасет не опубликован в root catalog, сетевой fetch тоже
  не выполняется; SMART-кандидаты дополнительно фильтруются по root catalog.

Шаг 6 (manual dataset Repair issue):
- Если пользователь вручную выбрал датасет, а root catalog успешно проверен
  и датасет больше не опубликован, создаём Repair issue.
- Для SMART Repair issue не создаётся: SMART просто пропускает такой кандидат.

Постоянный кэш:
- После успешного обновления сохраняем финальный raw_merged в Store.
- При старте используем совместимый persistent raw_merged, если latest run_id совпадает.
- Если сеть недоступна, используем совместимый persistent raw_merged как offline fallback.
- Для записей без прогноза сохраняем и восстанавливаем маленький current-кэш.
"""

import copy
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
from typing import Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .cache_runtime import SilamPollenCacheRuntime
from .const import (
    DOMAIN,
    RUNS_CATALOG_MANAGER,
    SILAM_CATALOG_MANAGER,
    THREDDS_ROOT_CATALOG_URL,
    URL_VAR_MAPPING,
    resolve_silam_var_name,
    DATASET_SRC_KEYS,
    SMART_MIN_COVERAGE_HOURS,
    SMART_NCSS_FAIL_STREAK_SWITCH,
)  # Импортируем константы и маппинг
from .repairs import (
    async_create_manual_dataset_unavailable_issue,
    async_delete_manual_dataset_unavailable_issue,
)


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
        cache_store=None,
        cached_payload=None,
        config_entry_id: str | None = None,
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
        :param cache_store: объект постоянного кэша для сохранения raw_merged.
        :param cached_payload: совместимый payload постоянного кэша, загруженный при setup.
        :param config_entry_id: идентификатор ConfigEntry для Repair issue.
        """
        self._base_device_name = base_device_name
        self._config_entry_id = config_entry_id
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
        # Последняя ошибка каталога нужна, чтобы отличать offline-сбой от пустого каталога.
        self._last_runs_catalog_error = None

        # Общий catalog-layer (domain-level) из hass.data[DOMAIN].
        # Root catalog используется для диагностики и как безопасный gate
        # в SMART-логике: retired-датасеты исключаются только если root
        # catalog успешно проверен и датасет явно отсутствует.
        domain_data = hass.data.get(DOMAIN, {})
        self._silam_catalog_manager = domain_data.get(SILAM_CATALOG_MANAGER)
        self._root_catalog_manager = getattr(self._silam_catalog_manager, "root", None)

        # Общий менеджер runs catalog (domain-level) из hass.data[DOMAIN].
        # Compatibility fallback оставлен для переходного периода: координатор
        # продолжает работать через прежний ключ RUNS_CATALOG_MANAGER.
        self._runs_manager = domain_data.get(RUNS_CATALOG_MANAGER)
        if self._runs_manager is None and self._silam_catalog_manager is not None:
            self._runs_manager = getattr(self._silam_catalog_manager, "runs", None)

        # Store постоянного кэша. Forecast-режим использует raw_merged,
        # non-forecast режим использует маленький current-кэш с последним now.
        # Runtime-логику восстановления/сохранения держим отдельно от координатора.
        self._cache_store = cache_store
        self._cached_payload = cached_payload if isinstance(cached_payload, dict) else None
        self._cache_runtime = SilamPollenCacheRuntime(self)

        # Одноразовый флаг для service action full_refresh.
        # При True координатор пропускает cache/synthetic/incremental пути
        # и выполняет полный сетевой запрос.
        self._force_full_refresh = False

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

        # --- Шаг 5b: root catalog hard gate ---
        # dataset_name -> причина исключения SMART-кандидата. Root catalog
        # также используется как ранний online-gate перед runs/NCSS fetch.
        self._smart_root_skipped: dict[str, str] = {}

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

    async def async_request_full_refresh(self):
        """Принудительно выполнить полный сетевой refresh без cache/incremental путей.

        В отличие от обычного обновления, full_refresh не должен
        восстанавливаться из cache. Если сетевой запрос не удался,
        сервисный вызов должен завершиться ошибкой, а существующий
        persistent cache должен остаться нетронутым.
        """
        self._force_full_refresh = True
        try:
            # Для service action нельзя использовать async_request_refresh():
            # он проходит через debouncer и при попадании в cooldown может не
            # выполнить refresh сразу. full_refresh должен быть синхронной
            # проверкой: вызов сервиса завершён только после реального refresh.
            await super().async_refresh()

            if not self.last_update_success:
                # DataUpdateCoordinator сохраняет исключение внутри себя и не
                # пробрасывает его наружу. Для service action full_refresh
                # явно превращаем неуспешный refresh в ошибку вызова сервиса.
                err = getattr(self, "last_exception", None)
                try:
                    self.async_update_listeners()
                except Exception as notify_err:  # noqa: BLE001 - ошибка уведомления не должна скрывать root cause
                    _LOGGER.debug(
                        "%s Failed to notify listeners after full refresh failure: %s",
                        self._log_prefix,
                        notify_err,
                    )
                if isinstance(err, Exception):
                    raise UpdateFailed(f"Forced full refresh failed: {err}") from err
                raise UpdateFailed("Forced full refresh failed")
        finally:
            self._force_full_refresh = False

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

    async def _fetch_latest_run_info_for_catalog_url(self, catalog_url: str | None):
        """Вернуть (run_id, start, end) для указанного runs/catalog.xml.

        Метод дополнительно запоминает последнюю ошибку каталога. Это нужно,
        чтобы ранний offline fallback включался только при сетевом сбое, а не
        при обычном пустом каталоге без latest run.
        """
        self._last_runs_catalog_error = None

        if not catalog_url:
            return None, None, None

        if self._runs_manager is None:
            _LOGGER.debug(
                "%s runs catalog: RunsCatalogManager is not initialized (url=%s)",
                self._log_prefix,
                catalog_url,
            )
            return None, None, None

        try:
            latest = await self._runs_manager.async_get_latest(catalog_url)

            get_last_error = getattr(self._runs_manager, "get_last_error", None)
            if callable(get_last_error):
                self._last_runs_catalog_error = get_last_error(catalog_url)

            if latest and latest.run_id:
                if self._last_runs_catalog_error:
                    _LOGGER.debug(
                        "%s runs catalog returned cached run after refresh error: "
                        "run=%s error=%s",
                        self._log_prefix,
                        latest.run_id,
                        self._last_runs_catalog_error,
                    )
                else:
                    _LOGGER.debug(
                        "%s runs catalog ok: run=%s start=%s end=%s",
                        self._log_prefix,
                        latest.run_id,
                        latest.start,
                        latest.end,
                    )
                return latest.run_id, latest.start, latest.end

            if self._last_runs_catalog_error:
                _LOGGER.debug(
                    "%s runs catalog failed: url=%s error=%s",
                    self._log_prefix,
                    catalog_url,
                    self._last_runs_catalog_error,
                )
            else:
                _LOGGER.debug(
                    "%s runs catalog has no latest run: url=%s",
                    self._log_prefix,
                    catalog_url,
                )
            return None, None, None

        except Exception as err:
            self._last_runs_catalog_error = str(err)
            _LOGGER.debug(
                "%s runs catalog failed: url=%s error=%s",
                self._log_prefix,
                catalog_url,
                err,
            )
            return None, None, None

    async def _fetch_latest_run_info(self, session):
        """Вернуть (run_id, start, end) из текущего runs/catalog.xml."""
        return await self._fetch_latest_run_info_for_catalog_url(self._runs_catalog_url)

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

    async def _get_root_info_for_smart(self):
        """Вернуть root catalog snapshot для SMART-фильтра кандидатов.

        Основная online-проверка выполняется раньше, в `_async_update_data()`.
        Здесь используем уже сохранённый snapshot через TTL/cache manager, чтобы
        не делать повторный сетевой запрос при каждом SMART-кандидате.
        """
        manager = self._root_catalog_manager
        if manager is None:
            return None

        try:
            return await manager.async_get_info()
        except Exception as err:  # noqa: BLE001 - SMART не должен падать из-за root check
            _LOGGER.debug(
                "%s SMART root catalog check skipped: %s",
                self._log_prefix,
                err,
            )
            return None

    def _smart_candidate_allowed_by_root_catalog(self, base_url: str, root_info) -> bool:
        """Проверить, можно ли SMART-кандидат использовать по root catalog.

        Возвращает False только в одном безопасном случае: root catalog успешно
        прошёл проверку, но dataset.path кандидата отсутствует в списке
        опубликованных датасетов. Недоступный root catalog обрабатывается раньше
        как hard gate, поэтому здесь fallback оставлен только как страховка.
        """
        manager = self._root_catalog_manager
        if manager is None or getattr(root_info, "ok", False) is not True:
            return True

        dataset_name = self._dataset_name_from_base_url(base_url)
        if dataset_name in (None, "", "-"):
            return True

        try:
            listed = manager.is_dataset_listed(dataset_name, root_info)
        except Exception as err:  # noqa: BLE001 - fallback к старой SMART-логике
            _LOGGER.debug(
                "%s SMART root catalog gate failed for %s: %s",
                self._log_prefix,
                dataset_name,
                err,
            )
            return True

        if listed is False:
            self._smart_root_skipped[dataset_name] = "dataset_not_listed"
            _LOGGER.debug(
                "%s SMART: skip candidate %s: dataset is not listed in SILAM root catalog",
                self._log_prefix,
                dataset_name,
            )
            return False

        return True

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
        self._smart_root_skipped = {}
        root_info = await self._get_root_info_for_smart()

        now_utc = datetime.now(timezone.utc)
        min_end_dt = now_utc + timedelta(hours=SMART_MIN_COVERAGE_HOURS)

        for url in candidates:
            if not url:
                continue

            # --- Шаг 5: root catalog gate для SMART-кандидатов ---
            # Исключаем retired-датасет только если root catalog сам успешно
            # проверен. При проблеме root catalog продолжаем старую логику,
            # чтобы временный сбой каталога не отключил все кандидаты.
            if not self._smart_candidate_allowed_by_root_catalog(url, root_info):
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
                            return url
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
                # Пробуем распарсить XML, если получилось — это покрытие
                ET.fromstring(txt)
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

    def _dataset_catalog_info_for_base_url(
        self,
        base_url: str | None,
        root_info=None,
    ) -> dict:
        """Вернуть диагностическую информацию о публикации датасета.

        Метод только читает root catalog snapshot и не влияет на выбор
        датасета. Если root catalog недоступен, `listed` остаётся None —
        это значит, что делать вывод об удалении датасета нельзя.
        """
        dataset_name = self._dataset_name_from_base_url(base_url)
        manager = self._root_catalog_manager
        listed = None
        catalog_info = None

        if manager is not None and dataset_name not in (None, "", "-"):
            try:
                listed = manager.is_dataset_listed(dataset_name, root_info)
                build_info = getattr(manager, "build_dataset_catalog_info", None)
                if callable(build_info):
                    catalog_info = build_info(dataset_name, root_info)
            except Exception as err:  # noqa: BLE001 - диагностика не должна ломать refresh
                _LOGGER.debug(
                    "%s root catalog dataset diagnostic failed for %s: %s",
                    self._log_prefix,
                    dataset_name,
                    err,
                )

        if not isinstance(catalog_info, dict):
            catalog_info = {
                "dataset_name": dataset_name,
                "listed": listed,
                "base_url": base_url,
                "runs_catalog_url": self._derive_runs_catalog_url_for_base_url(base_url),
            }
        else:
            catalog_info = dict(catalog_info)
            catalog_info.setdefault("dataset_name", dataset_name)
            catalog_info.setdefault("listed", listed)
            catalog_info.setdefault("base_url", base_url)
            catalog_info.setdefault(
                "runs_catalog_url",
                self._derive_runs_catalog_url_for_base_url(base_url),
            )

        return catalog_info

    async def _get_root_catalog_diagnostics(self, *, force_refresh: bool = False) -> dict:
        """Собрать диагностику root catalog без изменения поведения координатора.

        force_refresh=True используется для full_refresh/error paths, где
        статус службы должен отражать текущую сетевую доступность, а не
        только TTL-кэш последней успешной проверки.
        """
        manager = self._root_catalog_manager
        if manager is None:
            return {
                "url": THREDDS_ROOT_CATALOG_URL,
                "status": "manager_unavailable",
                "ok": None,
                "error": "root catalog manager is not initialized",
                "effective_dataset": self._dataset_name_from_base_url(self._base_url),
                "effective_dataset_listed": None,
                "preferred_dataset": self._dataset_name_from_base_url(self._preferred_base_url),
                "preferred_dataset_listed": None,
                "smart_root_skipped": dict(self._smart_root_skipped),
            }

        try:
            info = await manager.async_get_info(force_refresh=force_refresh)
        except Exception as err:  # noqa: BLE001 - диагностика не должна ломать refresh
            _LOGGER.debug("%s root catalog diagnostic refresh failed: %s", self._log_prefix, err)
            return {
                "url": THREDDS_ROOT_CATALOG_URL,
                "status": "unknown_error",
                "ok": False,
                "error": str(err),
                "effective_dataset": self._dataset_name_from_base_url(self._base_url),
                "effective_dataset_listed": None,
                "preferred_dataset": self._dataset_name_from_base_url(self._preferred_base_url),
                "preferred_dataset_listed": None,
                "smart_root_skipped": dict(self._smart_root_skipped),
            }

        effective = self._dataset_catalog_info_for_base_url(self._base_url, info)
        preferred = self._dataset_catalog_info_for_base_url(self._preferred_base_url, info)
        dataset_paths = sorted(getattr(info, "dataset_paths", frozenset()) or [])

        return {
            "url": THREDDS_ROOT_CATALOG_URL,
            "status": getattr(info, "status", None),
            "ok": getattr(info, "ok", None),
            "error": getattr(info, "error", None),
            "http_status": getattr(info, "http_status", None),
            "catalog_name": getattr(info, "catalog_name", None),
            "catalog_name_ok": getattr(info, "catalog_name_ok", None),
            "pollen_catalogs_ok": getattr(info, "pollen_catalogs_ok", None),
            "pollen_catalogs": list(getattr(info, "pollen_catalogs", ()) or ()),
            "dataset_paths_count": len(dataset_paths),
            "dataset_paths": dataset_paths,
            "effective_dataset": effective.get("dataset_name"),
            "effective_dataset_listed": effective.get("listed"),
            "effective_dataset_path": effective.get("path"),
            "effective_dataset_label": effective.get("label"),
            "preferred_dataset": preferred.get("dataset_name"),
            "preferred_dataset_listed": preferred.get("listed"),
            "preferred_dataset_path": preferred.get("path"),
            "preferred_dataset_label": preferred.get("label"),
            "fetched_at": (
                info.fetched_at.isoformat()
                if getattr(info, "fetched_at", None) is not None
                else None
            ),
            "last_ok": (
                info.last_ok.isoformat()
                if getattr(info, "last_ok", None) is not None
                else None
            ),
            "last_error": getattr(info, "last_error", None),
            "smart_root_skipped": dict(self._smart_root_skipped),
        }

    def _is_coverage_expired(self, latest_end: str | None) -> bool | None:
        """Проверить, достаточно ли далеко вперёд покрывает текущий latest run.

        Возвращает:
        - True  — coverage_end меньше now+SMART_MIN_COVERAGE_HOURS;
        - False — coverage_end есть и покрытие достаточно;
        - None  — coverage_end неизвестен или не парсится.
        """
        end_dt = self._parse_dt_utc(latest_end)
        if end_dt is None:
            return None
        return end_dt < (datetime.now(timezone.utc) + timedelta(hours=SMART_MIN_COVERAGE_HOURS))

    def _infer_service_reason(self, root_catalog_diag: dict) -> str:
        """Определить подробную причину состояния службы SILAM.

        Здесь возвращаем именно `reason`, а не короткое состояние сенсора.
        Короткое состояние строится отдельно в `_build_service_diagnostics()`.
        """
        root_status = root_catalog_diag.get("status")
        root_ok = root_catalog_diag.get("ok")
        effective_listed = root_catalog_diag.get("effective_dataset_listed")

        if root_status in (
            "manager_unavailable",
            "connection_error",
            "http_error",
            "ssl_error",
            "timeout",
            "unknown_error",
        ):
            return "root_catalog_unavailable"

        if root_status in (
            "catalog_error",
            "invalid_xml",
        ) or root_ok is False:
            return "root_catalog_invalid"

        if effective_listed is False:
            return "dataset_not_listed"

        runs_error = self._last_runs_catalog_error
        if runs_error and not self._latest_run_id:
            if runs_error == "parse: no latest run":
                return "runs_no_latest"
            return "runs_catalog_unavailable"

        if not self._latest_run_id:
            return "runs_no_latest"

        if self._is_coverage_expired(self._latest_run_end) is True:
            return "coverage_expired"

        return "none"

    @staticmethod
    def _service_state_from_reason(reason: str) -> str:
        """Преобразовать подробную причину в короткое состояние enum-сенсора."""
        if reason in (None, "", "none"):
            return "ok"
        if reason in ("root_catalog_unavailable", "root_catalog_invalid"):
            return "service_unavailable"
        if reason in (
            "dataset_not_listed",
            "runs_catalog_unavailable",
            "runs_no_latest",
            "coverage_expired",
            "no_dataset_available",
        ):
            return "dataset_unavailable"
        if reason in (
            "ncss_unavailable",
            "ncss_invalid_response",
            "ncss_empty_body",
        ):
            return "data_unavailable"
        return "unknown"

    def _build_service_diagnostics(
        self,
        *,
        root_catalog_diag: dict,
        request_type: str | None,
        cache_source: str | None,
        offline_fallback: bool,
    ) -> dict:
        """Собрать онлайн-статус службы SILAM и подробную причину.

        `service_status` описывает доступность внешней службы SILAM, а не
        источник данных конкретной ConfigEntry. Поэтому cache/offline fallback
        не переводит статус в отдельное состояние: сведения о кэше остаются
        в `diag.request` и диагностическом сенсоре fetch_duration.
        """
        reason = self._infer_service_reason(root_catalog_diag)
        status = self._service_state_from_reason(reason)

        return {
            "status": status,
            "reason": reason,
            "root_catalog_status": root_catalog_diag.get("status"),
            "root_catalog_ok": root_catalog_diag.get("ok"),
            "root_catalog_error": root_catalog_diag.get("error") or root_catalog_diag.get("last_error"),
            "dataset_selection": self._dataset_selection,
            "effective_dataset": root_catalog_diag.get("effective_dataset")
                or self._dataset_name_from_base_url(self._base_url),
            "effective_dataset_listed": root_catalog_diag.get("effective_dataset_listed"),
            "preferred_dataset": root_catalog_diag.get("preferred_dataset")
                or self._dataset_name_from_base_url(self._preferred_base_url),
            "preferred_dataset_listed": root_catalog_diag.get("preferred_dataset_listed"),
            "smart_root_skipped": root_catalog_diag.get("smart_root_skipped")
                or dict(self._smart_root_skipped),
        }

    def _is_manual_dataset_selection(self) -> bool:
        """Вернуть True, если пользователь выбрал фиксированный датасет вручную."""
        return (self._dataset_selection or "smart").lower() != "smart"

    async def _async_create_manual_dataset_repair_if_needed(
        self,
        root_catalog_diag: dict,
    ) -> None:
        """Создать Repair issue для ручного датасета, отсутствующего в root catalog."""
        if not self._is_manual_dataset_selection():
            return

        if root_catalog_diag.get("ok") is not True:
            return

        if root_catalog_diag.get("effective_dataset_listed") is not False:
            return

        await async_create_manual_dataset_unavailable_issue(
            self.hass,
            entry_id=self._config_entry_id,
            entry_title=self._base_device_name,
            dataset_name=root_catalog_diag.get("effective_dataset")
            or self._dataset_name_from_base_url(self._base_url),
        )

    async def _async_clear_manual_dataset_repair_if_needed(
        self,
        root_catalog_diag: dict,
    ) -> None:
        """Удалить Repair issue, если ручной датасет снова доступен или выбран SMART."""
        if not self._config_entry_id:
            return

        if not self._is_manual_dataset_selection():
            await async_delete_manual_dataset_unavailable_issue(
                self.hass,
                entry_id=self._config_entry_id,
            )
            return

        if (
            root_catalog_diag.get("ok") is True
            and root_catalog_diag.get("effective_dataset_listed") is True
        ):
            await async_delete_manual_dataset_unavailable_issue(
                self.hass,
                entry_id=self._config_entry_id,
            )

    def _root_catalog_hard_gate_reason(self, root_catalog_diag: dict) -> str | None:
        """Вернуть причину, если online-проверка root catalog запрещает сетевой fetch.

        Этот gate стоит перед SMART, runs/catalog.xml и NCSS. Если root catalog
        недоступен или текущий датасет не опубликован, дальше в сеть не идём.
        """
        root_status = root_catalog_diag.get("status")
        root_ok = root_catalog_diag.get("ok")
        effective_listed = root_catalog_diag.get("effective_dataset_listed")

        if root_status in (
            "manager_unavailable",
            "connection_error",
            "http_error",
            "ssl_error",
            "timeout",
            "unknown_error",
        ):
            return "root_catalog_unavailable"

        if root_status in (
            "catalog_error",
            "invalid_xml",
        ) or root_ok is False:
            return "root_catalog_invalid"

        if root_ok is True and effective_listed is False:
            # Для ручного выбора это ошибка настройки пользователя: дальше в сеть
            # не идём и создаём Repair issue. Для SMART это не hard gate:
            # SMART сам отфильтрует отсутствующий кандидат и попробует следующий.
            if self._is_manual_dataset_selection():
                return "dataset_not_listed"
            return None

        return None

    def _build_root_catalog_gate_error(
        self,
        *,
        root_catalog_diag: dict,
        reason: str,
    ) -> UpdateFailed:
        """Собрать понятную ошибку hard gate без дополнительных сетевых действий."""
        status = root_catalog_diag.get("status")
        error = root_catalog_diag.get("error") or root_catalog_diag.get("last_error")
        dataset = root_catalog_diag.get("effective_dataset")

        details = [f"reason={reason}", f"status={status}"]
        if dataset:
            details.append(f"dataset={dataset}")
        if error:
            details.append(f"error={error}")

        return UpdateFailed(
            "SILAM root catalog hard gate failed: " + ", ".join(details)
        )

    @staticmethod
    def _reason_from_fetch_error(err: Exception) -> str:
        """Определить service reason по ошибке сетевого/NCSS-запроса."""
        if isinstance(err, ET.ParseError):
            msg = str(err).lower()
            if "no element found" in msg:
                return "ncss_empty_body"
            return "ncss_invalid_response"

        if isinstance(err, (asyncio.TimeoutError, aiohttp.ClientError)):
            return "ncss_unavailable"

        return "ncss_unavailable"

    def _override_service_reason_if_needed(
        self,
        service_diag: dict,
        *,
        fallback_reason: str,
    ) -> dict:
        """Подставить причину ошибки, если catalog-диагностика не дала точной причины."""
        diag = dict(service_diag)
        reason = diag.get("reason")
        if reason in (None, "", "none"):
            diag["reason"] = fallback_reason
            diag["status"] = self._service_state_from_reason(fallback_reason)
        return diag

    async def _publish_failed_refresh_diagnostics(
        self,
        *,
        request_type: str | None,
        err: Exception,
        started_at: float,
        force_root_refresh: bool,
        root_catalog_diag: dict | None = None,
    ) -> None:
        """Обновить service diagnostics после неуспешного refresh без перезаписи кэша.

        Метод сохраняет старые пользовательские данные в `merged_data`, но
        обновляет диагностический блок, чтобы `service_status` видел причину
        отказа даже тогда, когда DataUpdateCoordinator завершает refresh
        через UpdateFailed. Persistent cache здесь намеренно не сохраняется.
        """
        if root_catalog_diag is None:
            root_catalog_diag = await self._get_root_catalog_diagnostics(
                force_refresh=force_root_refresh
            )
        fallback_reason = self._reason_from_fetch_error(err)
        service_diag = self._build_service_diagnostics(
            root_catalog_diag=root_catalog_diag,
            request_type=request_type,
            cache_source=None,
            offline_fallback=False,
        )
        service_diag = self._override_service_reason_if_needed(
            service_diag,
            fallback_reason=fallback_reason,
        )
        service_diag["error"] = f"{type(err).__name__}: {err}"

        current = dict(self.merged_data) if isinstance(self.merged_data, dict) else {}
        diag = dict(current.get("diag")) if isinstance(current.get("diag"), dict) else {}
        diag["service"] = service_diag
        diag["root_catalog"] = root_catalog_diag
        diag["runs_catalog"] = {
            "url": self._runs_catalog_url,
            "latest_run_id": self._latest_run_id,
            "latest_run_start": self._latest_run_start,
            "latest_run_end": self._latest_run_end,
        }
        diag["request"] = {
            "type": request_type,
            "cache_source": None,
            "offline_fallback": False,
            "failed": True,
            "error": f"{type(err).__name__}: {err}",
            "tail_fetch_attempted": False,
            "tail_fetch_network": False,
            "tail_fetch_success": None,
        }
        diag["dataset"] = {
            "selection": self._dataset_selection,
            "effective_base_url": self._base_url,
            "preferred_base_url": self._preferred_base_url,
        }
        diag["cache"] = self._cache_runtime.persistent_cache_diagnostics(None)
        current["diag"] = diag
        current["last_fetch_duration"] = round(time.monotonic() - started_at, 3)
        self.merged_data = current

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
        # full_forced  : принудительный полный сетевой фетч через service action
        # synthetic    : пересборка только из кеша raw_merged (без сети)
        # incremental  : кеш + частичный сетевой запрос (догрузка хвоста)
        force_full_refresh = self._force_full_refresh
        request_type = 'full_forced' if force_full_refresh else 'full'
        tail_fetch_attempted = False
        tail_fetch_network = False
        tail_fetch_success = None
        offline_fallback = False
        # Флаг меняется только когда raw_merged реально расширен сетевыми данными.
        # Простая пересборка из RAM/persistent cache не должна перезаписывать Store.
        persistent_cache_changed = False

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
        cache_source = None
        use_incremental = False
        raw_all = None
        merged_override = None
        run_id = None
        run_start = None
        run_end = None
        root_catalog_diag = {
            "url": THREDDS_ROOT_CATALOG_URL,
            "status": "not_checked",
            "ok": None,
            "error": None,
            "effective_dataset": self._dataset_name_from_base_url(self._base_url),
            "effective_dataset_listed": None,
            "preferred_dataset": self._dataset_name_from_base_url(self._preferred_base_url),
            "preferred_dataset_listed": None,
            "smart_root_skipped": dict(self._smart_root_skipped),
        }

        try:
            async with aiohttp.ClientSession() as session:
                # --- Шаг 5b: root catalog hard gate ---
                # Это обязательная online-проверка перед SMART, runs/catalog.xml
                # и NCSS. При ошибке root catalog дальше в сеть не идём.
                self._prof(t0, "before_root_catalog_gate")
                root_catalog_diag = await self._get_root_catalog_diagnostics(force_refresh=True)
                self._prof(t0, "after_root_catalog_gate")

                root_gate_reason = self._root_catalog_hard_gate_reason(root_catalog_diag)
                if root_gate_reason == "dataset_not_listed":
                    await self._async_create_manual_dataset_repair_if_needed(root_catalog_diag)
                elif root_gate_reason is None:
                    await self._async_clear_manual_dataset_repair_if_needed(root_catalog_diag)

                if root_gate_reason is not None:
                    err = self._build_root_catalog_gate_error(
                        root_catalog_diag=root_catalog_diag,
                        reason=root_gate_reason,
                    )
                    raise err

                # --- Раннее восстановление из persistent cache ---
                # CacheRuntime сам решает, можно ли использовать forecast raw_merged,
                # non-forecast current или stale fallback. Координатор только
                # выполняет раннюю проверку каталога и применяет готовый результат.
                cache_catalog_base_url = None if force_full_refresh else self._cache_runtime.early_catalog_base_url()
                if cache_catalog_base_url:
                    stale_catalog_url = self._derive_runs_catalog_url_for_base_url(
                        cache_catalog_base_url
                    )
                    self._prof(t0, "before_early_runs_catalog")
                    pre_run_id, _pre_run_start, _pre_run_end = (
                        await self._fetch_latest_run_info_for_catalog_url(stale_catalog_url)
                    )
                    self._prof(t0, "after_early_runs_catalog")

                    early_restore = self._cache_runtime.prepare_early_restore(
                        pre_run_id=pre_run_id,
                        run_start=_pre_run_start,
                        run_end=_pre_run_end,
                        catalog_error=self._last_runs_catalog_error,
                    )
                    if early_restore is not None:
                        if early_restore.get("index") is not None:
                            data["index"] = early_restore["index"]
                        raw_all_ref = early_restore.get("raw_all_ref")
                        raw_view = early_restore.get("raw_view")
                        merged_override = early_restore.get("merged_override")
                        src_ds = early_restore.get("src_ds")
                        src_key = early_restore.get("src_key")
                        run_id = early_restore.get("run_id")
                        run_start = early_restore.get("run_start")
                        run_end = early_restore.get("run_end")

                        latest_run_id = early_restore.get("latest_run_id")
                        if latest_run_id is not None:
                            self._latest_run_id = latest_run_id
                            self._latest_run_start = early_restore.get("latest_run_start")
                            self._latest_run_end = early_restore.get("latest_run_end")

                        active_run_id = early_restore.get("active_run_id")
                        if active_run_id:
                            self._active_run_id = active_run_id

                        request_type = early_restore["request_type"]
                        cache_source = early_restore["cache_source"]
                        offline_fallback = early_restore["offline_fallback"]
                        use_incremental = True
                        tail_fetch_attempted = early_restore["tail_fetch_attempted"]
                        tail_fetch_network = early_restore["tail_fetch_network"]
                        tail_fetch_success = early_restore["tail_fetch_success"]

                if not use_incremental:
                    # --- Шаг 3: SMART-выбор датасета (один раз на старте/первом обновлении) ---
                    self._prof(t0, "before_smart_selection")
                    await self._apply_smart_selection_if_needed(session, latitude, longitude)
                    self._prof(t0, "after_smart_selection")

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
                if not use_incremental and self._dataset_selection == "smart":
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
                # Шаг 2/3: если run_id не изменился, пересобираем из кеша raw_merged.
                # Сначала используем runtime-кэш в памяти, а после рестарта HA —
                # совместимый persistent cache, если его run_id совпадает с каталогом.
                # -----------------------------------------------------------------
                self._prof(t0, "before_incremental_if")
                if not use_incremental and not force_full_refresh:
                    raw_all, cache_source = (
                        self._cache_runtime.prepare_online_restore_candidate(run_id)
                    )

                if not use_incremental and isinstance(raw_all, dict) and raw_all:
                    self._prof(t0, "entered_incremental_if")
                    raw_all_ref = raw_all  # важно: дальше Шаг 2b/Шаг 4 расширяют именно этот dict

                    # Проставляем источник для старых кешей, где меток ещё не было
                    self._apply_src_to_raw(raw_all, src_key)

                    # «Сдвигаем окно» по текущему времени:
                    # - чуть захватываем прошлое (1 час), чтобы не ломать текущую семантику "now"
                    # - конец окна = now + forecast_duration
                    window_start, window_end = self._cache_runtime.current_forecast_window()

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
                                        persistent_cache_changed = True
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

                                    root_info_for_fill = await self._get_root_info_for_smart()

                                    for cand in (self._smart_candidates or []):
                                        if not cand or cand == self._base_url:
                                            continue

                                        # Не используем retired-кандидаты при дозаполнении missing-times.
                                        if not self._smart_candidate_allowed_by_root_catalog(cand, root_info_for_fill):
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

                                            if add_cnt > 0:
                                                persistent_cache_changed = True

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

                    rebuild = self._cache_runtime.prepare_synthetic_rebuild_from_raw(
                        raw_all,
                        run_id=run_id,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    if rebuild is not None:
                        raw_all_ref = rebuild["raw_all_ref"]
                        raw_view = rebuild["raw_view"]
                        src_ds = rebuild["src_ds"]
                        src_key = rebuild["src_key"]

                        # Если хвост не догружали — это чисто синтетическая пересборка из кеша.
                        # Если хвост догружали — это инкрементальный режим (кеш + частичный сетевой фетч).
                        request_type = 'incremental' if tail_fetch_network else 'synthetic'
                        if cache_source == "persistent":
                            self._active_run_id = run_id

                        _LOGGER.debug(
                            "%s Cache rebuild mode=%s source=%s run_id=%s points=%s/%s",
                            self._log_prefix,
                            request_type,
                            cache_source,
                            run_id,
                            rebuild["points_view"],
                            rebuild["points_total"],
                        )
                        data["index"] = rebuild["index"]
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
            if force_full_refresh:
                await self._publish_failed_refresh_diagnostics(
                    request_type=request_type,
                    err=err,
                    started_at=start,
                    force_root_refresh=False,
                    root_catalog_diag=root_catalog_diag,
                )
                _LOGGER.debug(
                    "%s Forced full refresh failed; cache fallback is intentionally disabled: %s",
                    self._log_prefix,
                    err,
                )
                raise UpdateFailed(f"Forced full refresh failed: {err}") from err

            # Поздний fallback остаётся страховкой для ошибок после ранней
            # проверки каталога: SMART probe, index/main fetch или tail fetch.
            late_restore = self._cache_runtime.prepare_late_restore(err)
            if late_restore is None:
                await self._publish_failed_refresh_diagnostics(
                    request_type=request_type,
                    err=err,
                    started_at=start,
                    force_root_refresh=False,
                    root_catalog_diag=root_catalog_diag,
                )
                raise UpdateFailed(f"Ошибка при получении или обработке XML: {err}") from err

            if late_restore.get("index") is not None:
                data["index"] = late_restore["index"]
            raw_all_ref = late_restore.get("raw_all_ref")
            raw_view = late_restore.get("raw_view")
            merged_override = late_restore.get("merged_override")
            src_ds = late_restore.get("src_ds")
            src_key = late_restore.get("src_key")
            run_id = late_restore.get("run_id")
            run_start = late_restore.get("run_start")
            run_end = late_restore.get("run_end")

            active_run_id = late_restore.get("active_run_id")
            if active_run_id:
                self._active_run_id = active_run_id

            request_type = late_restore["request_type"]
            cache_source = late_restore["cache_source"]
            offline_fallback = late_restore["offline_fallback"]
            use_incremental = True
            tail_fetch_attempted = late_restore["tail_fetch_attempted"]
            tail_fetch_network = late_restore["tail_fetch_network"]
            tail_fetch_success = late_restore["tail_fetch_success"]

        # Объединяем данные один раз и кешируем в merged_data,
        # при этом оригинальный словарь data возвращается как есть для совместимости
        try:
            from .data_processing import merge_station_features

            if isinstance(merged_override, dict):
                merged = copy.deepcopy(merged_override)
            else:
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
            # После возможного SMART-переключения обновляем dataset-поля
            # root catalog диагностики. Повторного сетевого запроса нет: snapshot
            # уже обновлён hard gate в начале refresh.
            root_catalog_diag = await self._get_root_catalog_diagnostics()

            # Засекаем конец и вычисляем длительность фетча
            duration = time.monotonic() - start
            merged["last_fetch_duration"] = round(duration, 3)

            service_diag = self._build_service_diagnostics(
                root_catalog_diag=root_catalog_diag,
                request_type=request_type,
                cache_source=cache_source,
                offline_fallback=offline_fallback,
            )

            merged["diag"] = {
            # --- Короткий статус службы SILAM для отдельного диагностического сенсора ---
            "service": service_diag,
            # --- runs catalog (диагностика) ---
            "runs_catalog": {
                "url": self._runs_catalog_url,
                "latest_run_id": self._latest_run_id,
                "latest_run_start": self._latest_run_start,
                "latest_run_end": self._latest_run_end,
            },
            # --- Root catalog hard gate + диагностика ---
            "root_catalog": root_catalog_diag,
            # --- Диагностика типа запроса (для SilamPollenFetchDurationSensor) ---
            "request": {
                "type": request_type,
                "cache_source": cache_source,
                "offline_fallback": offline_fallback,
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
            # --- Постоянный кэш (для диагностического сенсора) ---
            "cache": self._cache_runtime.persistent_cache_diagnostics(cache_source),
            }

            _LOGGER.debug(
                "%s Сформированные объединённые данные (fetch duration: %.3fs): %s",
                self._log_prefix,
                duration,
                #merged,
                merged.get("diag"),
            )
            self.merged_data = {**merged}

            await self._cache_runtime.async_save_after_update(
                merged=merged,
                request_type=request_type,
                cache_source=cache_source,
                offline_fallback=offline_fallback,
                tail_fetch_success=tail_fetch_success,
                changed=persistent_cache_changed,
            )

            # После сетевого сохранения или offline fallback обновляем cache-диагностику,
            # чтобы диагностический сенсор видел актуальный источник данных.
            if isinstance(self.merged_data, dict):
                diag = self.merged_data.get("diag")
                if isinstance(diag, dict):
                    diag["cache"] = self._cache_runtime.persistent_cache_diagnostics(cache_source)
        except Exception as err:
            _LOGGER.error("%s Ошибка при объединении или обработке прогнозных данных: %s", self._log_prefix, err)
            self.merged_data = {}
