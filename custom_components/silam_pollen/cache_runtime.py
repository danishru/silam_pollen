"""Runtime-helper для persistent cache SILAM Pollen.

Модуль содержит логику восстановления и сохранения runtime-кэша, чтобы
`coordinator.py` отвечал в основном за оркестрацию обновления, а не за детали
payload постоянного кэша.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

_LOGGER = logging.getLogger(__name__)


class SilamPollenCacheRuntime:
    """Помощник координатора для runtime-операций persistent cache."""

    def __init__(self, coordinator: Any) -> None:
        """Сохранить ссылку на координатор без жёсткого импорта его класса."""
        self._coordinator = coordinator

    async def async_save_persistent_cache(self, merged: dict) -> None:
        """Сохранить постоянный runtime-кэш, если Store подключён."""
        c = self._coordinator
        try:
            cache_store = c._cache_store
            if cache_store is None:
                return

            raw_merged = merged.get("raw_merged") if isinstance(merged, dict) else None
            current = merged.get("now") if isinstance(merged, dict) else None
            has_raw = isinstance(raw_merged, dict) and bool(raw_merged)
            has_current = isinstance(current, dict) and bool(current)
            if not has_raw and not has_current:
                _LOGGER.debug(
                    "%s Persistent cache save skipped: raw_merged and current are empty",
                    c._log_prefix,
                )
                return

            if not c._active_run_id:
                _LOGGER.debug(
                    "%s Persistent cache save skipped: active run_id is missing",
                    c._log_prefix,
                )
                return

            await cache_store.async_save_runtime_cache(
                raw_merged=raw_merged if isinstance(raw_merged, dict) else {},
                current=current if isinstance(current, dict) else None,
                active_run_id=c._active_run_id,
                effective_base_url=c._base_url,
                preferred_base_url=c._preferred_base_url,
            )
        except Exception as err:  # noqa: BLE001 - запись кэша не должна ломать обновление
            _LOGGER.warning(
                "%s Failed to persist cache after update: %s",
                c._log_prefix,
                err,
            )

    def persistent_cache_diagnostics(self, cache_source: str | None) -> dict:
        """Собрать диагностические сведения о постоянном кэше."""
        c = self._coordinator
        cache_store = c._cache_store
        if cache_store is None:
            return {
                "enabled": False,
                "source": cache_source,
                "loaded": False,
                "compatible": False,
                "schema_version": None,
                "saved_at": None,
                "entry_title": None,
                "active_run_id": None,
                "effective_base_url": None,
                "preferred_base_url": None,
                "points": 0,
                "current_available": False,
                "current_date": None,
                "current_data_points": 0,
                "restore_payload_loaded": isinstance(c._cached_payload, dict),
            }

        info = dict(cache_store.cache_info)
        info["enabled"] = True
        info["source"] = cache_source
        info["restore_payload_loaded"] = isinstance(c._cached_payload, dict)
        return info

    def prepare_online_restore_candidate(self, run_id: str | None) -> tuple[dict | None, str | None]:
        """Вернуть raw_merged и источник для online-восстановления по run_id.

        Сначала используется runtime-кэш в памяти. После рестарта HA, когда
        памяти ещё нет, используется совместимый persistent cache, если его
        run_id совпадает с каталогом. Метод только выбирает источник данных
        и не выполняет synthetic-пересборку.
        """
        c = self._coordinator
        if not c._forecast_enabled or not run_id:
            return None, None

        if (
            c._active_run_id == run_id
            and isinstance(c.merged_data, dict)
            and isinstance(c.merged_data.get("raw_merged"), dict)
        ):
            raw_all = c.merged_data.get("raw_merged") or {}
            if raw_all:
                return raw_all, "memory"

        raw_all = self.get_persistent_raw_merged_for_run(run_id)
        if isinstance(raw_all, dict) and raw_all:
            return raw_all, "persistent"

        return None, None

    async def async_save_after_update(
        self,
        *,
        merged: dict,
        request_type: str | None,
        cache_source: str | None,
        offline_fallback: bool,
        tail_fetch_success: bool | None,
        changed: bool,
    ) -> None:
        """Сохранить persistent cache после обновления, если это действительно нужно.

        Cache-файл обновляется только после реального сетевого обновления или
        расширения raw_merged. Synthetic-пересборка из memory/persistent cache
        не должна сдвигать saved_at и перезаписывать тот же payload без новых
        данных.
        """
        c = self._coordinator
        should_save = (
            not offline_fallback
            and (
                request_type == "full"
                or tail_fetch_success is True
                or changed
            )
        )
        if should_save:
            await self.async_save_persistent_cache(merged)
            return

        _LOGGER.debug(
            "%s Persistent cache save skipped: request_type=%s cache_source=%s "
            "offline_fallback=%s tail_fetch_success=%s changed=%s",
            c._log_prefix,
            request_type,
            cache_source,
            offline_fallback,
            tail_fetch_success,
            changed,
        )

    def get_persistent_raw_merged_for_run(self, run_id: str | None) -> dict | None:
        """Вернуть raw_merged из постоянного кэша, если он подходит текущему run_id."""
        c = self._coordinator
        payload = c._cached_payload
        if not isinstance(payload, dict) or not run_id:
            return None

        dataset = payload.get("dataset")
        if not isinstance(dataset, dict):
            return None

        cached_run_id = dataset.get("active_run_id")
        if cached_run_id != run_id:
            return None

        cached_base_url = dataset.get("effective_base_url")
        if cached_base_url and cached_base_url != c._base_url:
            _LOGGER.debug(
                "%s Persistent cache restore skipped: base_url mismatch",
                c._log_prefix,
            )
            return None

        raw_merged = payload.get("raw_merged")
        if not isinstance(raw_merged, dict) or not raw_merged:
            return None

        return copy.deepcopy(raw_merged)

    def get_persistent_stale_raw_merged(self) -> tuple[dict | None, str | None, str | None]:
        """Вернуть raw_merged из постоянного кэша для offline fallback.

        Этот режим используется только когда сетевое обновление не удалось.
        Run ID не проверяется через каталог, поэтому данные считаются устаревшими.
        Третий элемент нужен, чтобы при SMART восстановить последний effective_base_url.
        """
        c = self._coordinator
        payload = c._cached_payload
        if not isinstance(payload, dict):
            return None, None, None

        dataset = payload.get("dataset")
        if not isinstance(dataset, dict):
            return None, None, None

        cached_run_id = dataset.get("active_run_id")
        if not cached_run_id:
            return None, None, None

        raw_merged = payload.get("raw_merged")
        if not isinstance(raw_merged, dict) or not raw_merged:
            return None, None, None

        cached_base_url = dataset.get("effective_base_url")
        cached_base_url = str(cached_base_url) if cached_base_url else None
        return copy.deepcopy(raw_merged), str(cached_run_id), cached_base_url

    def get_persistent_stale_current(self) -> tuple[dict | None, str | None, str | None]:
        """Вернуть current payload из постоянного кэша для non-forecast fallback.

        Этот кэш используется только для записей без прогноза, где `raw_merged`
        специально не хранится. Run ID проверяется отдельно, а при offline
        fallback данные считаются устаревшими.
        """
        c = self._coordinator
        payload = c._cached_payload
        if not isinstance(payload, dict):
            return None, None, None

        dataset = payload.get("dataset")
        if not isinstance(dataset, dict):
            return None, None, None

        cached_run_id = dataset.get("active_run_id")
        if not cached_run_id:
            return None, None, None

        current = payload.get("current")
        if not isinstance(current, dict) or not current:
            return None, None, None

        current_data = current.get("data")
        if not isinstance(current_data, dict) or not current_data:
            return None, None, None

        cached_base_url = dataset.get("effective_base_url")
        cached_base_url = str(cached_base_url) if cached_base_url else None
        return copy.deepcopy(current), str(cached_run_id), cached_base_url

    def early_catalog_base_url(self) -> str | None:
        """Вернуть base_url для ранней проверки каталога по cache payload.

        Координатору нужен только URL каталога. Все детали о том, есть ли
        forecast raw_merged или non-forecast current cache, остаются внутри
        cache-runtime слоя.
        """
        c = self._coordinator
        stale_raw, _stale_run_id, stale_base_url = self.get_persistent_stale_raw_merged()
        stale_current, _current_run_id, current_base_url = self.get_persistent_stale_current()

        has_raw_cache = isinstance(stale_raw, dict) and bool(stale_raw)
        has_current_cache = (
            not c._forecast_enabled
            and isinstance(stale_current, dict)
            and bool(stale_current)
        )
        if not has_raw_cache and not has_current_cache:
            return None

        return stale_base_url or current_base_url or c._base_url

    def prepare_early_restore(
        self,
        *,
        pre_run_id: str | None,
        run_start: Any = None,
        run_end: Any = None,
        catalog_error: str | None = None,
    ) -> dict[str, Any] | None:
        """Подготовить раннее восстановление из persistent cache.

        Метод принимает результат ранней проверки runs/catalog и решает, можно
        ли сразу подняться из кэша. Координатор остаётся только оркестратором:
        он получает готовый набор полей и применяет его к локальным переменным
        текущего обновления.
        """
        c = self._coordinator
        stale_raw, stale_run_id, stale_base_url = self.get_persistent_stale_raw_merged()
        stale_current, current_run_id, current_base_url = self.get_persistent_stale_current()

        has_raw_cache = isinstance(stale_raw, dict) and bool(stale_raw)
        has_current_cache = (
            not c._forecast_enabled
            and isinstance(stale_current, dict)
            and bool(stale_current)
        )
        if not has_raw_cache and not has_current_cache:
            return None

        if has_raw_cache and pre_run_id and stale_run_id == pre_run_id:
            # Если RAM-кэш уже есть, не перехватываем поток: обычная memory-ветка
            # координатора сможет отработать позже и при необходимости выполнит SMART.
            has_memory_cache = (
                c._active_run_id == pre_run_id
                and isinstance(c.merged_data, dict)
                and isinstance(c.merged_data.get("raw_merged"), dict)
                and bool(c.merged_data.get("raw_merged"))
            )
            if not has_memory_cache:
                fallback = self.prepare_synthetic_rebuild_from_raw(
                    stale_raw,
                    run_id=pre_run_id,
                    source_base_url=stale_base_url,
                    switch_to_base_url=True,
                )
                if fallback is not None:
                    _LOGGER.debug(
                        "%s Fast persistent cache restore: run_id=%s points=%s/%s",
                        c._log_prefix,
                        pre_run_id,
                        fallback["points_view"],
                        fallback["points_total"],
                    )
                    return self._build_restore_result(
                        request_type="synthetic",
                        cache_source="persistent",
                        offline_fallback=False,
                        run_id=pre_run_id,
                        run_start=run_start,
                        run_end=run_end,
                        latest_run_id=pre_run_id,
                        latest_run_start=run_start,
                        latest_run_end=run_end,
                        active_run_id=pre_run_id,
                        index=fallback["index"],
                        raw_all_ref=fallback["raw_all_ref"],
                        raw_view=fallback["raw_view"],
                        src_ds=fallback["src_ds"],
                        src_key=fallback["src_key"],
                    )

                _LOGGER.debug(
                    "%s Fast persistent cache restore skipped: no points in current window",
                    c._log_prefix,
                )

        if has_current_cache and pre_run_id and current_run_id == pre_run_id:
            current_restore = self.prepare_current_restore_from_cache(
                stale_current,
                source_base_url=current_base_url,
                switch_to_base_url=True,
            )
            if current_restore is not None:
                _LOGGER.debug(
                    "%s Fast current cache restore: run_id=%s date=%s",
                    c._log_prefix,
                    pre_run_id,
                    stale_current.get("date"),
                )
                return self._build_restore_result(
                    request_type="synthetic",
                    cache_source="persistent_current",
                    offline_fallback=False,
                    run_id=pre_run_id,
                    run_start=run_start,
                    run_end=run_end,
                    latest_run_id=pre_run_id,
                    latest_run_start=run_start,
                    latest_run_end=run_end,
                    active_run_id=pre_run_id,
                    merged_override=current_restore["merged"],
                    src_ds=current_restore["src_ds"],
                    src_key=current_restore["src_key"],
                )

        if has_raw_cache and pre_run_id is None and catalog_error:
            fallback = self.prepare_synthetic_rebuild_from_raw(
                stale_raw,
                run_id=stale_run_id,
                source_base_url=stale_base_url,
                switch_to_base_url=True,
            )
            if fallback is not None:
                _LOGGER.warning(
                    "%s Offline fallback: restored persistent cache after runs catalog error: %s",
                    c._log_prefix,
                    catalog_error,
                )
                return self._build_restore_result(
                    request_type="synthetic",
                    cache_source="persistent_stale",
                    offline_fallback=True,
                    active_run_id=stale_run_id,
                    index=fallback["index"],
                    raw_all_ref=fallback["raw_all_ref"],
                    raw_view=fallback["raw_view"],
                    src_ds=fallback["src_ds"],
                    src_key=fallback["src_key"],
                )

            _LOGGER.debug(
                "%s Offline fallback skipped: persistent cache has no points in current window",
                c._log_prefix,
            )

        if has_current_cache and catalog_error:
            current_restore = self.prepare_current_restore_from_cache(
                stale_current,
                source_base_url=current_base_url,
                switch_to_base_url=True,
            )
            if current_restore is not None:
                _LOGGER.warning(
                    "%s Offline fallback: restored current cache after runs catalog error: %s",
                    c._log_prefix,
                    catalog_error,
                )
                return self._build_restore_result(
                    request_type="synthetic",
                    cache_source="persistent_current_stale",
                    offline_fallback=True,
                    active_run_id=current_run_id,
                    merged_override=current_restore["merged"],
                    src_ds=current_restore["src_ds"],
                    src_key=current_restore["src_key"],
                )

        return None

    def prepare_late_restore(self, err: Exception) -> dict[str, Any] | None:
        """Подготовить поздний offline fallback после ошибки сетевого обновления.

        Ранний fallback срабатывает сразу после ошибки runs/catalog. Этот метод
        остаётся страховкой для случаев, когда ошибка произошла позже: на
        SMART probe, index/main fetch, tail fetch или другой сетевой операции.
        """
        c = self._coordinator

        stale_raw, stale_run_id, stale_base_url = self.get_persistent_stale_raw_merged()
        if isinstance(stale_raw, dict) and stale_raw:
            fallback = self.prepare_synthetic_rebuild_from_raw(
                stale_raw,
                run_id=stale_run_id,
                source_base_url=stale_base_url,
                switch_to_base_url=True,
            )
            if fallback is not None:
                _LOGGER.warning(
                    "%s Offline fallback: restored persistent cache after update error: %s",
                    c._log_prefix,
                    err,
                )
                return self._build_restore_result(
                    request_type="synthetic",
                    cache_source="persistent_stale",
                    offline_fallback=True,
                    active_run_id=stale_run_id,
                    index=fallback["index"],
                    raw_all_ref=fallback["raw_all_ref"],
                    raw_view=fallback["raw_view"],
                    src_ds=fallback["src_ds"],
                    src_key=fallback["src_key"],
                )

            _LOGGER.warning(
                "%s Offline fallback skipped: persistent cache has no points in current window",
                c._log_prefix,
            )
            return None

        stale_current, current_run_id, current_base_url = self.get_persistent_stale_current()
        if (
            not c._forecast_enabled
            and isinstance(stale_current, dict)
            and stale_current
        ):
            current_restore = self.prepare_current_restore_from_cache(
                stale_current,
                source_base_url=current_base_url,
                switch_to_base_url=True,
            )
            if current_restore is not None:
                _LOGGER.warning(
                    "%s Offline fallback: restored current cache after update error: %s",
                    c._log_prefix,
                    err,
                )
                return self._build_restore_result(
                    request_type="synthetic",
                    cache_source="persistent_current_stale",
                    offline_fallback=True,
                    active_run_id=current_run_id,
                    merged_override=current_restore["merged"],
                    src_ds=current_restore["src_ds"],
                    src_key=current_restore["src_key"],
                )

        return None

    @staticmethod
    def _build_restore_result(
        *,
        request_type: str,
        cache_source: str,
        offline_fallback: bool,
        run_id: str | None = None,
        run_start: Any = None,
        run_end: Any = None,
        latest_run_id: str | None = None,
        latest_run_start: Any = None,
        latest_run_end: Any = None,
        active_run_id: str | None = None,
        index: Any = None,
        raw_all_ref: dict | None = None,
        raw_view: dict | None = None,
        merged_override: dict | None = None,
        src_ds: str | None = None,
        src_key: str | None = None,
    ) -> dict[str, Any]:
        """Собрать единый результат раннего восстановления для координатора."""
        return {
            "request_type": request_type,
            "cache_source": cache_source,
            "offline_fallback": offline_fallback,
            "run_id": run_id,
            "run_start": run_start,
            "run_end": run_end,
            "latest_run_id": latest_run_id,
            "latest_run_start": latest_run_start,
            "latest_run_end": latest_run_end,
            "active_run_id": active_run_id,
            "index": index,
            "raw_all_ref": raw_all_ref,
            "raw_view": raw_view,
            "merged_override": merged_override,
            "src_ds": src_ds,
            "src_key": src_key,
            "tail_fetch_attempted": False,
            "tail_fetch_network": False,
            "tail_fetch_success": None,
        }

    def prepare_current_restore_from_cache(
        self,
        current: dict,
        *,
        source_base_url: str | None = None,
        switch_to_base_url: bool = False,
    ) -> dict[str, Any] | None:
        """Подготовить merged payload из маленького current-кэша.

        Используется только для non-forecast режима. Не выполняет сетевых
        запросов и не создаёт forecast/raw_merged данные.
        """
        c = self._coordinator
        if not isinstance(current, dict) or not isinstance(current.get("data"), dict):
            return None

        if switch_to_base_url and source_base_url and source_base_url != c._base_url:
            # При SMART после перезапуска текущий base_url может быть исходным
            # из ConfigEntry. Для restore возвращаем last-known effective.
            c._set_base_url(source_base_url)

        src_ds = c._dataset_name_from_base_url(c._base_url)
        src_key = c._src_key_for_dataset(src_ds)
        return {
            "merged": {
                "now": copy.deepcopy(current),
                "hourly_forecast": [],
                "twice_daily_forecast": [],
                "daily_forecast": [],
            },
            "src_ds": src_ds,
            "src_key": src_key,
        }

    def current_forecast_window(self) -> tuple[datetime, datetime]:
        """Вернуть рабочее окно synthetic-пересборки относительно текущего времени."""
        c = self._coordinator
        now_utc = datetime.now(timezone.utc)
        return (
            now_utc - timedelta(hours=1),
            now_utc + timedelta(hours=c._forecast_duration),
        )

    def prepare_synthetic_rebuild_from_raw(
        self,
        raw_merged: dict,
        *,
        run_id: str | None,
        source_base_url: str | None = None,
        switch_to_base_url: bool = False,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Подготовить synthetic-пересборку из raw_merged одним общим способом.

        Метод используется для RAM cache, persistent cache и offline fallback.
        Он не выполняет сетевых запросов: только выбирает окно времени,
        восстанавливает метки источника и строит минимальный StationFeature XML.
        """
        c = self._coordinator
        if not isinstance(raw_merged, dict) or not raw_merged:
            return None

        if switch_to_base_url and source_base_url and source_base_url != c._base_url:
            # При SMART после перезапуска без сети текущий base_url может быть
            # исходным из ConfigEntry. Для stale-режима возвращаем last-known effective.
            c._set_base_url(source_base_url)

        src_ds = c._dataset_name_from_base_url(c._base_url)
        src_key = c._src_key_for_dataset(src_ds)

        # Проставляем источник только там, где его ещё нет. Уже смешанные SMART-данные
        # с собственными 's' не перетираем.
        c._apply_src_to_raw(raw_merged, src_key)

        if window_start is None or window_end is None:
            window_start, window_end = self.current_forecast_window()

        raw_view = {}
        for k, v in raw_merged.items():
            dt = c._parse_dt_utc(k)
            if dt is None:
                continue
            if window_start <= dt <= window_end:
                raw_view[k] = v

        if not raw_view:
            return None

        return {
            "index": c._build_station_features_xml_from_raw_merged(raw_view),
            "raw_all_ref": raw_merged,
            "raw_view": raw_view,
            "src_ds": src_ds,
            "src_key": src_key,
            "run_id": run_id,
            "points_total": len(raw_merged),
            "points_view": len(raw_view),
        }
