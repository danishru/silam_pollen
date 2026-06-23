"""Catalog managers for SILAM THREDDS.

Шаг 1: модуль переименован из runs_catalog.py в silam_catalog.py.
Шаг 2: добавлен фасад SilamCatalogManager как единая точка доступа
к catalog-слою SILAM.
Шаг 3: добавлен RootCatalogManager для проверки корневого THREDDS-каталога
SILAM и списка опубликованных pollen-датасетов.

Важно: на этом шаге SMART-логика и координатор не меняются. RootCatalogManager
только централизует уже существующую проверку из Config Flow и готовит API
для следующих аккуратных шагов.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import async_timeout
import xml.etree.ElementTree as ET

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DATASETS,
    THREDDS_CATALOG_NS,
    THREDDS_ROOT_CATALOG_NAME,
    THREDDS_ROOT_CATALOG_TIMEOUT_SECONDS,
    THREDDS_ROOT_CATALOG_URL,
    dataset_base_url,
)

_LOGGER = logging.getLogger(__name__)



@dataclass(slots=True)
class RootCatalogInfo:
    """Снимок состояния корневого THREDDS-каталога SILAM.

    Формат намеренно совместим с прежним dict-результатом Config Flow:
    `http_ok`, `ssl_ok`, `catalog_name_ok`, `pollen_catalogs_ok` и `error`
    используются теми же проверками формы настройки.
    """

    completed: bool = True
    status: str = "unknown"
    http_ok: bool = False
    http_status: int | None = None
    ssl_ok: bool | None = None
    catalog_name_ok: bool | None = None
    catalog_name: str | None = None
    pollen_catalogs_ok: bool | None = None
    pollen_catalogs: tuple[str, ...] = ()
    dataset_paths: frozenset[str] = field(default_factory=frozenset)
    error: str | None = None
    fetched_at: datetime | None = None
    last_ok: datetime | None = None
    last_error: str | None = None

    @property
    def ok(self) -> bool:
        """Вернуть True, если root catalog полностью прошёл проверку."""
        return all(
            value is True
            for value in (
                self.http_ok,
                self.ssl_ok,
                self.catalog_name_ok,
                self.pollen_catalogs_ok,
            )
        )

    def as_dict(self) -> dict:
        """Вернуть dict-совместимый результат для Config Flow и диагностики."""
        return {
            "completed": self.completed,
            "status": self.status,
            "http_ok": self.http_ok,
            "http_status": self.http_status,
            "ssl_ok": self.ssl_ok,
            "catalog_name_ok": self.catalog_name_ok,
            "catalog_name": self.catalog_name,
            "pollen_catalogs_ok": self.pollen_catalogs_ok,
            "pollen_catalogs": list(self.pollen_catalogs) if self.pollen_catalogs else None,
            "dataset_paths": sorted(self.dataset_paths),
            "error": self.error,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "last_ok": self.last_ok.isoformat() if self.last_ok else None,
            "last_error": self.last_error,
        }


@dataclass(slots=True)
class _RootCatalogState:
    """Runtime-состояние root catalog cache."""

    info: RootCatalogInfo = field(default_factory=RootCatalogInfo)
    last_ok: Optional[datetime] = None
    last_attempt: Optional[datetime] = None
    last_error: Optional[str] = None
    inflight: Optional[asyncio.Task] = None


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



class RootCatalogManager:
    """Domain-level менеджер корневого THREDDS-каталога SILAM.

    Менеджер выполняет ту же проверку, которая раньше жила в Config Flow:
    HTTP/SSL, корректность XML, имя root catalog и наличие pollen-каталогов.
    Дополнительно он собирает опубликованные dataset paths, чтобы на следующих
    шагах можно было исключать retired-датасеты из SMART-логики.
    """

    def __init__(self, hass, *, ttl_seconds: int = 600) -> None:
        self._hass = hass
        self._ttl = timedelta(seconds=ttl_seconds)
        self._state = _RootCatalogState()

    def _is_fresh(self) -> bool:
        """Вернуть True, если последняя успешная проверка ещё свежая."""
        if not self._state.last_ok:
            return False
        return (datetime.utcnow() - self._state.last_ok) <= self._ttl

    def get_last_error(self) -> Optional[str]:
        """Вернуть последнюю ошибку проверки root catalog."""
        return self._state.last_error

    def is_dataset_listed(
        self,
        dataset_name: str,
        info: RootCatalogInfo | None = None,
    ) -> bool | None:
        """Проверить, опубликован ли датасет в root catalog.

        Возвращает:
        - True  — root catalog успешно проверен, dataset.path найден;
        - False — root catalog успешно проверен, dataset.path не найден;
        - None  — root catalog не прошёл проверку, делать вывод нельзя.
        """
        root_info = info or self._state.info
        if not root_info.ok:
            return None

        try:
            dataset_path = DATASETS[dataset_name].path
        except KeyError:
            dataset_path = dataset_name

        return dataset_path in root_info.dataset_paths

    def build_dataset_catalog_info(
        self,
        dataset_name: str,
        info: RootCatalogInfo | None = None,
    ) -> dict:
        """Вернуть компактную информацию о датасете из root catalog.

        Метод пока не используется координатором. Он нужен как безопасная
        подготовка к следующим шагам: SMART-фильтру и предупреждениям для
        ручного выбора retired-датасетов.
        """
        listed = self.is_dataset_listed(dataset_name, info)
        try:
            meta = DATASETS[dataset_name]
            base_url = dataset_base_url(dataset_name)
            path = meta.path
            file_name = meta.file
            label = meta.label
        except KeyError:
            base_url = None
            path = dataset_name
            file_name = None
            label = None

        runs_catalog_url = self._derive_runs_catalog_url_for_base_url(base_url)
        return {
            "dataset_name": dataset_name,
            "path": path,
            "file": file_name,
            "label": label,
            "listed": listed,
            "base_url": base_url,
            "runs_catalog_url": runs_catalog_url,
        }

    async def async_get_info(self, *, force_refresh: bool = False) -> RootCatalogInfo:
        """Вернуть снимок состояния root catalog.

        - По умолчанию используется TTL-кэш.
        - force_refresh=True нужен Config Flow, чтобы сохранить прежнее поведение:
          при открытии/подтверждении формы выполняется актуальная проверка.
        """
        st = self._state

        if not force_refresh and self._is_fresh():
            _LOGGER.debug(
                "root catalog cache hit: %s (age=%ss)",
                THREDDS_ROOT_CATALOG_URL,
                int((datetime.utcnow() - st.last_ok).total_seconds()),
            )
            return st.info

        if st.inflight and not st.inflight.done():
            _LOGGER.debug("root catalog await inflight: %s", THREDDS_ROOT_CATALOG_URL)
            try:
                await st.inflight
            except Exception:
                # Ошибка уже сохранена в состоянии; отдаём текущий снимок.
                pass
            return st.info

        _LOGGER.debug("root catalog refresh: %s", THREDDS_ROOT_CATALOG_URL)
        st.inflight = self._hass.async_create_task(self._async_refresh())
        try:
            await st.inflight
        finally:
            if st.inflight and st.inflight.done():
                st.inflight = None
        return st.info

    async def _async_refresh(self) -> None:
        st = self._state
        st.last_attempt = datetime.utcnow()
        session = async_get_clientsession(self._hass)

        info = RootCatalogInfo(status="unknown")

        try:
            async with async_timeout.timeout(THREDDS_ROOT_CATALOG_TIMEOUT_SECONDS):
                async with session.get(THREDDS_ROOT_CATALOG_URL) as response:
                    # Полученный HTTPS-ответ означает, что стандартная SSL-проверка
                    # общей aiohttp-сессии Home Assistant успешно пройдена.
                    info.ssl_ok = True
                    info.http_status = response.status
                    info.http_ok = response.status == 200

                    if response.status != 200:
                        info.status = "http_error"
                        info.error = "http_error"
                        st.info = info
                        st.last_error = f"HTTP {response.status}"
                        _LOGGER.debug(
                            "root catalog HTTP %s: %s",
                            response.status,
                            THREDDS_ROOT_CATALOG_URL,
                        )
                        return

                    xml_text = await response.text()

        except (
            aiohttp.ClientConnectorCertificateError,
            aiohttp.ClientConnectorSSLError,
            ssl.CertificateError,
            ssl.SSLError,
        ) as err:
            info.ssl_ok = False
            info.status = "ssl_error"
            info.error = "ssl_error"
            info.last_error = str(err)
            st.info = info
            st.last_error = f"{type(err).__name__}: {err}"
            _LOGGER.debug("SILAM root catalog SSL check failed: %s", err)
            return
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            info.status = "connection_error"
            info.error = "connection_error"
            info.last_error = str(err)
            st.info = info
            st.last_error = f"{type(err).__name__}: {err}"
            _LOGGER.debug("SILAM root catalog availability check failed: %s", err)
            return
        except Exception as err:  # noqa: BLE001 - root check не должен ломать Config Flow
            info.status = "unknown_error"
            info.error = "unknown_error"
            info.last_error = str(err)
            st.info = info
            st.last_error = f"{type(err).__name__}: {err}"
            _LOGGER.debug("Unexpected SILAM root catalog check error: %s", err)
            return

        try:
            parsed = self._parse_root_catalog(xml_text)
        except ET.ParseError as err:
            info.status = "invalid_xml"
            info.error = "invalid_xml"
            info.last_error = str(err)
            st.info = info
            st.last_error = f"ParseError: {err}"
            _LOGGER.debug("SILAM root catalog returned invalid XML: %s", err)
            return
        except Exception as err:  # noqa: BLE001 - защита от неожиданной структуры XML
            info.status = "unknown_error"
            info.error = "unknown_error"
            info.last_error = str(err)
            st.info = info
            st.last_error = f"{type(err).__name__}: {err}"
            _LOGGER.debug("Unexpected SILAM root catalog parse error: %s", err)
            return

        parsed.http_ok = info.http_ok
        parsed.http_status = info.http_status
        parsed.ssl_ok = info.ssl_ok
        parsed.fetched_at = datetime.utcnow()

        if parsed.ok:
            parsed.status = "ok"
            parsed.error = None
            parsed.last_ok = parsed.fetched_at
            parsed.last_error = None
            st.last_ok = parsed.fetched_at
            st.last_error = None
            _LOGGER.debug(
                "root catalog ok: name=%s pollen_catalogs=%s dataset_paths=%s",
                parsed.catalog_name,
                parsed.pollen_catalogs,
                sorted(parsed.dataset_paths),
            )
        else:
            # Для совместимости с прежним Config Flow error оставляем None:
            # _catalog_check_error_key() уже смотрит catalog_name_ok/pollen_catalogs_ok.
            parsed.status = "catalog_error"
            parsed.last_error = "catalog structure check failed"
            st.last_error = parsed.last_error
            _LOGGER.debug(
                "root catalog structure check failed: name_ok=%s pollen_catalogs_ok=%s name=%s",
                parsed.catalog_name_ok,
                parsed.pollen_catalogs_ok,
                parsed.catalog_name,
            )

        st.info = parsed

    def _parse_root_catalog(self, xml_text: str) -> RootCatalogInfo:
        """Распарсить root catalog и вернуть RootCatalogInfo без HTTP-полей."""
        root = ET.fromstring(xml_text)

        catalog_name = root.attrib.get("name")
        catalog_refs = root.findall(".//t:catalogRef", THREDDS_CATALOG_NS)

        pollen_catalogs = sorted(
            {
                catalog_ref.attrib.get("name", "")
                for catalog_ref in catalog_refs
                if "pollen" in catalog_ref.attrib.get("name", "").lower()
            }
        )
        dataset_paths = self._extract_dataset_paths(catalog_refs)

        return RootCatalogInfo(
            status="ok",
            catalog_name=catalog_name,
            catalog_name_ok=catalog_name == THREDDS_ROOT_CATALOG_NAME,
            pollen_catalogs=tuple(pollen_catalogs),
            pollen_catalogs_ok=bool(pollen_catalogs),
            dataset_paths=frozenset(dataset_paths),
        )

    @staticmethod
    def _extract_dataset_paths(catalog_refs: list[ET.Element]) -> set[str]:
        """Извлечь имена опубликованных pollen-датасетов из catalogRef."""
        dataset_paths: set[str] = set()

        for catalog_ref in catalog_refs:
            values = [
                catalog_ref.attrib.get("name"),
                catalog_ref.attrib.get("href"),
                catalog_ref.attrib.get("xlink:href"),
                catalog_ref.attrib.get("{http://www.w3.org/1999/xlink}href"),
            ]

            for value in values:
                if not value:
                    continue
                for part in RootCatalogManager._candidate_path_parts(str(value)):
                    if "pollen" in part.lower():
                        dataset_paths.add(part)

        return dataset_paths

    @staticmethod
    def _candidate_path_parts(value: str) -> tuple[str, ...]:
        """Вернуть возможные сегменты пути из name/href catalogRef."""
        raw = value.strip()
        if not raw:
            return tuple()

        # catalogRef href может быть относительным или абсолютным URL.
        parsed = urlparse(raw)
        path = parsed.path if parsed.scheme and parsed.netloc else raw
        path = path.split("?", 1)[0].strip("/")
        if not path:
            return tuple()

        parts = tuple(
            part
            for part in path.split("/")
            if part and part != "catalog.xml"
        )
        return parts

    @staticmethod
    def _derive_runs_catalog_url_for_base_url(base_url: str | None) -> str | None:
        """Строит URL runs/catalog.xml по NCSS base_url датасета."""
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

    def get_last_error(self, catalog_url: str | None) -> Optional[str]:
        """Вернуть последнюю ошибку refresh для указанного каталога.

        Координатор использует это для раннего offline fallback: если latest run
        не получен именно из-за сетевой ошибки, можно сразу восстановиться из
        persistent cache и не ждать дополнительные таймауты index/main fetch.
        """
        if not catalog_url:
            return None
        st = self._states.get(catalog_url)
        return st.last_error if st else None

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

class SilamCatalogManager:
    """Единая точка доступа к catalog-слою SILAM.

    root отвечает за корневой THREDDS-каталог и список опубликованных
    датасетов. runs сохраняет прежнюю ответственность: latest run и coverage
    для конкретного runs/catalog.xml.
    """

    def __init__(
        self,
        hass,
        *,
        ttl_seconds: int = 600,
        root_manager: RootCatalogManager | None = None,
        runs_manager: RunsCatalogManager | None = None,
    ) -> None:
        """Создать общий catalog-manager для DOMAIN.

        runs_manager используется только для мягкого hot-reload: если старый
        RunsCatalogManager уже был создан под legacy-ключом, фасад переиспользует
        его и не теряет текущий TTL-кэш. root_manager оставлен симметрично для
        будущих тестов/hot-reload сценариев.
        """
        self.root = root_manager or RootCatalogManager(
            hass,
            ttl_seconds=ttl_seconds,
        )
        self.runs = runs_manager or RunsCatalogManager(
            hass,
            ttl_seconds=ttl_seconds,
        )
