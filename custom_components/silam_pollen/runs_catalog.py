"""Runs catalog manager for SILAM THREDDS.

Общий (domain-level) кэш runs/catalog.xml для всех записей интеграции.
Цели:
- не дергать один и тот же каталог N раз при N ConfigEntry
- дедуплицировать параллельные запросы
- хранить общий timeCoverage (start/end) по всем runs (и в будущем — список runs)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import async_timeout
import xml.etree.ElementTree as ET

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import THREDDS_CATALOG_NS

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LatestRunInfo:
    """Снимок latest run из runs/catalog.xml.

    Важно:
    - run_id: latest run (обычно первый в списке)
    - start/end: общий coverage по всем runs (min start / max end)
    """

    run_id: Optional[str] = None
    # В каталоге это timeCoverage.start/end (обычно ISO-строка в UTC, иногда с Z)
    start: Optional[str] = None
    end: Optional[str] = None
    # Для отладки
    fetched_at: Optional[datetime] = None


@dataclass(slots=True)
class _CatalogState:
    latest: LatestRunInfo
    last_ok: Optional[datetime] = None
    last_attempt: Optional[datetime] = None
    last_error: Optional[str] = None
    inflight: Optional[asyncio.Task] = None


class RunsCatalogManager:
    """Domain-level менеджер runs catalog (TTL-кэш + дедуп запросов)."""

    def __init__(self, hass, *, ttl_seconds: int = 600) -> None:
        self._hass = hass
        self._ttl = timedelta(seconds=ttl_seconds)
        self._states: dict[str, _CatalogState] = {}

    def _state(self, catalog_url: str) -> _CatalogState:
        st = self._states.get(catalog_url)
        if st is None:
            st = _CatalogState(latest=LatestRunInfo())
            self._states[catalog_url] = st
        return st

    def _is_fresh(self, st: _CatalogState) -> bool:
        if not st.last_ok:
            return False
        return (datetime.utcnow() - st.last_ok) <= self._ttl

    async def async_get_latest(self, catalog_url: str) -> LatestRunInfo:
        """Вернуть LatestRunInfo.

        - Если кэш свежий: отдаём сразу.
        - Если есть inflight: ждём его.
        - Иначе: обновляем.
        """
        st = self._state(catalog_url)

        if self._is_fresh(st):
            _LOGGER.debug(
                "runs catalog cache hit: %s (age=%ss)",
                catalog_url,
                int((datetime.utcnow() - st.last_ok).total_seconds()),
            )
            return st.latest

        if st.inflight and not st.inflight.done():
            _LOGGER.debug("runs catalog await inflight: %s", catalog_url)
            try:
                await st.inflight
            except Exception:
                # Ошибка уже залогирована внутри inflight; отдаём то, что есть в кэше
                pass
            return st.latest

        _LOGGER.debug("runs catalog refresh: %s", catalog_url)
        st.inflight = self._hass.async_create_task(self._async_refresh(catalog_url))
        try:
            await st.inflight
        finally:
            # inflight чистим только если это именно текущий task
            if st.inflight and st.inflight.done():
                st.inflight = None
        return st.latest

    async def _async_refresh(self, catalog_url: str) -> None:
        st = self._state(catalog_url)
        st.last_attempt = datetime.utcnow()

        session = async_get_clientsession(self._hass)

        try:
            async with async_timeout.timeout(10):
                async with session.get(catalog_url) as resp:
                    if resp.status != 200:
                        st.last_error = f"HTTP {resp.status}"
                        _LOGGER.debug("runs catalog HTTP %s: %s", resp.status, catalog_url)
                        return
                    xml_text = await resp.text()

            latest = self._parse_latest(xml_text)
            if latest.run_id:
                latest.fetched_at = datetime.utcnow()
                st.latest = latest
                st.last_ok = latest.fetched_at
                st.last_error = None
                _LOGGER.debug(
                    "runs catalog ok: %s run=%s coverage_start=%s coverage_end=%s",
                    catalog_url,
                    latest.run_id,
                    latest.start,
                    latest.end,
                )
            else:
                st.last_error = "parse: no latest run"
                _LOGGER.debug("runs catalog parse: no latest run in %s", catalog_url)

        except Exception as err:
            st.last_error = f"{type(err).__name__}: {err}"
            _LOGGER.debug("runs catalog error: %s (%s)", catalog_url, err)

    def _parse_latest(self, xml_text: str) -> LatestRunInfo:
        def _parse_iso(s: str | None) -> datetime | None:
            if not s:
                return None
            try:
                # поддерживаем ...Z
                if s.endswith("Z"):
                    return datetime.fromisoformat(s[:-1])
                return datetime.fromisoformat(s)
            except Exception:
                return None

        root = ET.fromstring(xml_text)

        parent = root.find(".//t:dataset[@name='Forecast Model Run']", THREDDS_CATALOG_NS)
        if parent is None:
            return LatestRunInfo()

        runs = parent.findall("t:dataset", THREDDS_CATALOG_NS)
        if not runs:
            return LatestRunInfo()

        # latest run_id — оставляем как “первый в списке” (обычно самый свежий)
        run_id = runs[0].get("name")

        min_start_dt: datetime | None = None
        min_start_raw: str | None = None
        max_end_dt: datetime | None = None
        max_end_raw: str | None = None

        for ds in runs:
            start_el = ds.find("t:timeCoverage/t:start", THREDDS_CATALOG_NS)
            end_el = ds.find("t:timeCoverage/t:end", THREDDS_CATALOG_NS)
            start_raw = start_el.text.strip() if (start_el is not None and start_el.text) else None
            end_raw = end_el.text.strip() if (end_el is not None and end_el.text) else None

            start_dt = _parse_iso(start_raw)
            end_dt = _parse_iso(end_raw)

            if start_dt is not None and (min_start_dt is None or start_dt < min_start_dt):
                min_start_dt = start_dt
                min_start_raw = start_raw

            if end_dt is not None and (max_end_dt is None or end_dt > max_end_dt):
                max_end_dt = end_dt
                max_end_raw = end_raw

        return LatestRunInfo(run_id=run_id, start=min_start_raw, end=max_end_raw)
