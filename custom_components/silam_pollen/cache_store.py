"""Хелперы постоянного кэша для SILAM Pollen.

Шаг 1: безопасный каркас постоянного кэша.
Шаг 2: сохранение финального `raw_merged` после успешного обновления.
Шаг 3: возврат совместимого payload координатору для восстановления при старте.
Шаг 4: отдельный current-кэш для записей без прогноза.

Хелпер создаёт/читает Store для конкретной ConfigEntry, формирует
метаданные совместимости и сохраняет источник данных. Для forecast-режима
основным источником остаётся `raw_merged`, для non-forecast fallback
дополнительно сохраняется последний готовый `now` payload. Само
восстановление выполняет координатор только после проверки run_id или
при offline fallback.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_MISSING: Final = object()

CACHE_SCHEMA_VERSION = 1
CACHE_STORAGE_VERSION = 1
CACHE_STORAGE_DIR = DOMAIN
CACHE_STORAGE_FILE_PREFIX = "cache"


def _cache_storage_key(entry_id: str) -> str:
    """Вернуть ключ Home Assistant Store для cache-файла одной ConfigEntry."""
    return f"{CACHE_STORAGE_DIR}/{CACHE_STORAGE_FILE_PREFIX}.{entry_id}"


class SilamPollenCacheStore:
    """Обёртка постоянного cache Store для одной ConfigEntry.

    Хранит каркас, метаданные совместимости, финальный `raw_merged`
    для forecast-режима и последний `now` payload для non-forecast режима.
    При setup возвращает совместимый payload, но решение о восстановлении
    принимает координатор.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        base_url: str,
        selected_allergens: list[str],
        forecast_enabled: bool,
        forecast_duration: int,
        dataset_selection: str,
        latitude: Any,
        longitude: Any,
        altitude: Any,
    ) -> None:
        self._entry = entry
        self._log_prefix = f"[{entry.title}]"
        self._fingerprint = self._build_entry_fingerprint(
            entry=entry,
            base_url=base_url,
            selected_allergens=selected_allergens,
            forecast_enabled=forecast_enabled,
            forecast_duration=forecast_duration,
            dataset_selection=dataset_selection,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
        )
        self._store = Store(
            hass,
            CACHE_STORAGE_VERSION,
            _cache_storage_key(entry.entry_id),
        )
        self._last_data: dict[str, Any] | None = None

    @property
    def entry_fingerprint(self) -> dict[str, Any]:
        """Вернуть метаданные, определяющие совместимое состояние ConfigEntry."""
        return dict(self._fingerprint)

    @property
    def cache_info(self) -> dict[str, Any]:
        """Вернуть компактные сведения о текущем payload кэша для диагностики."""
        data = self._last_data
        if not isinstance(data, dict):
            return {
                "loaded": False,
                "compatible": False,
                "schema_version": None,
                "saved_at": None,
                "entry_title": self._entry.title,
                "active_run_id": None,
                "effective_base_url": None,
                "preferred_base_url": None,
                "points": 0,
                "current_available": False,
                "current_date": None,
                "current_data_points": 0,
            }

        raw_merged = data.get("raw_merged")
        current = data.get("current")
        current_data = current.get("data") if isinstance(current, dict) else None
        dataset = data.get("dataset")
        if not isinstance(dataset, dict):
            dataset = {}

        return {
            "loaded": True,
            "compatible": self.is_compatible(data),
            "schema_version": data.get("schema_version"),
            "saved_at": data.get("saved_at"),
            "entry_title": data.get("entry_title"),
            "active_run_id": dataset.get("active_run_id"),
            "effective_base_url": dataset.get("effective_base_url"),
            "preferred_base_url": dataset.get("preferred_base_url"),
            "points": len(raw_merged) if isinstance(raw_merged, dict) else 0,
            "current_available": isinstance(current, dict) and bool(current),
            "current_date": current.get("date") if isinstance(current, dict) else None,
            "current_data_points": len(current_data) if isinstance(current_data, dict) else 0,
        }

    async def async_initialize(self) -> dict[str, Any] | None:
        """Загрузить существующий каркас кэша или создать пустой, если его нет.

        Возвращает совместимый payload, если он уже есть. На несовместимый или
        повреждённый payload не падает и не перезаписывает его — только логирует.
        """
        data = await self._async_load_raw()
        if data is _MISSING:
            await self.async_save_shell()
            _LOGGER.debug("%s Persistent cache shell initialized", self._log_prefix)
            return None
        if data is None:
            return None

        self._last_data = data
        if not self.is_compatible(data):
            _LOGGER.debug(
                "%s Persistent cache shell loaded but is not compatible with current entry",
                self._log_prefix,
            )
            return None

        raw_merged = data.get("raw_merged")
        current = data.get("current")
        points = len(raw_merged) if isinstance(raw_merged, dict) else 0
        _LOGGER.debug(
            "%s Persistent cache shell loaded: schema=%s points=%s current=%s saved_at=%s",
            self._log_prefix,
            data.get("schema_version"),
            points,
            isinstance(current, dict) and bool(current),
            data.get("saved_at"),
        )
        return data

    async def async_save_shell(self) -> None:
        """Сохранить пустой каркас кэша для этой ConfigEntry."""
        payload = self.build_payload(raw_merged={}, current=None)
        payload["saved_at"] = None
        try:
            await self._store.async_save(payload)
        except Exception as err:  # noqa: BLE001 - ошибка хранилища не должна ломать setup
            _LOGGER.warning(
                "%s Failed to save persistent cache shell: %s",
                self._log_prefix,
                err,
            )
            return
        self._last_data = payload

    async def async_save_runtime_cache(
        self,
        *,
        raw_merged: dict[str, Any] | None,
        current: dict[str, Any] | None = None,
        active_run_id: str | None,
        effective_base_url: str | None,
        preferred_base_url: str | None,
    ) -> None:
        """Сохранить runtime-кэш после успешного обновления координатора.

        Для forecast-режима сохраняется `raw_merged`. Для non-forecast режима
        дополнительно сохраняется последний готовый `now` payload. Ошибка
        записи только логируется и не прерывает обновление сущностей.
        """
        raw_payload = raw_merged if isinstance(raw_merged, dict) else {}
        current_payload = current if isinstance(current, dict) and current else None
        if not raw_payload and current_payload is None:
            _LOGGER.debug(
                "%s Persistent cache save skipped: raw_merged and current are empty",
                self._log_prefix,
            )
            return

        payload = self.build_payload(
            raw_merged=copy.deepcopy(raw_payload),
            current=copy.deepcopy(current_payload) if current_payload is not None else None,
            active_run_id=active_run_id,
            effective_base_url=effective_base_url,
            preferred_base_url=preferred_base_url,
        )
        try:
            await self._store.async_save(payload)
        except Exception as err:  # noqa: BLE001 - ошибка хранилища не должна ломать обновление
            _LOGGER.warning(
                "%s Failed to save persistent cache: %s",
                self._log_prefix,
                err,
            )
            return

        self._last_data = payload
        _LOGGER.debug(
            "%s Persistent cache saved: run_id=%s points=%s current=%s",
            self._log_prefix,
            active_run_id,
            len(raw_payload),
            current_payload is not None,
        )

    async def async_remove(self) -> None:
        """Удалить cache-файл этой ConfigEntry из хранилища Home Assistant."""
        try:
            await self._store.async_remove()
        except Exception as err:  # noqa: BLE001 - очистка не должна ломать удаление записи
            _LOGGER.warning(
                "%s Failed to remove persistent cache file: %s",
                self._log_prefix,
                err,
            )
            return
        self._last_data = None
        _LOGGER.debug("%s Persistent cache file removed", self._log_prefix)

    def build_payload(
        self,
        *,
        raw_merged: dict[str, Any] | None,
        current: dict[str, Any] | None = None,
        active_run_id: str | None = None,
        effective_base_url: str | None = None,
        preferred_base_url: str | None = None,
    ) -> dict[str, Any]:
        """Собрать JSON-сериализуемый payload кэша.

        Используется для пустого shell, forecast-кэша `raw_merged` и
        маленького non-forecast кэша `current`. Поле `entry_title` нужно
        только для удобного чтения cache-файла человеком и не участвует
        в fingerprint совместимости.
        """
        has_payload = bool(raw_merged) or bool(current)
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "saved_at": self._utcnow_iso() if has_payload else None,
            "entry_title": self._entry.title,
            "entry": dict(self._fingerprint),
            "dataset": {
                "active_run_id": active_run_id,
                "effective_base_url": effective_base_url,
                "preferred_base_url": preferred_base_url,
            },
            "raw_merged": raw_merged or {},
            "current": current or {},
        }

    def is_compatible(self, data: dict[str, Any]) -> bool:
        """Вернуть True, если сохранённый payload относится к текущей записи/настройкам."""
        if not isinstance(data, dict):
            return False
        if data.get("schema_version") != CACHE_SCHEMA_VERSION:
            return False
        if data.get("entry") != self._fingerprint:
            return False
        raw_merged = data.get("raw_merged")
        current = data.get("current", {})
        return isinstance(raw_merged, dict) and isinstance(current, dict)

    async def _async_load_raw(self) -> dict[str, Any] | None | object:
        """Загрузить сырой payload Store, не ломая setup интеграции при ошибках хранилища."""
        try:
            data = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 - ошибка хранилища не должна ломать setup
            _LOGGER.warning(
                "%s Failed to load persistent cache shell: %s",
                self._log_prefix,
                err,
            )
            return None

        if data is None:
            return _MISSING
        if not isinstance(data, dict):
            _LOGGER.warning(
                "%s Persistent cache shell has invalid root type: %s",
                self._log_prefix,
                type(data).__name__,
            )
            return None
        return data

    @classmethod
    def _build_entry_fingerprint(
        cls,
        *,
        entry: ConfigEntry,
        base_url: str,
        selected_allergens: list[str],
        forecast_enabled: bool,
        forecast_duration: int,
        dataset_selection: str,
        latitude: Any,
        longitude: Any,
        altitude: Any,
    ) -> dict[str, Any]:
        """Собрать fingerprint совместимости для кэшированных данных."""
        return {
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
            "coordinates_fingerprint": cls._coordinates_fingerprint(
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
            ),
            "selected_allergens": sorted(str(v) for v in (selected_allergens or [])),
            "forecast_enabled": bool(forecast_enabled),
            "forecast_duration": int(forecast_duration),
            "dataset_selection": str(dataset_selection or "smart").lower(),
            "configured_base_url": base_url,
        }

    @classmethod
    def _coordinates_fingerprint(
        cls,
        *,
        latitude: Any,
        longitude: Any,
        altitude: Any,
    ) -> dict[str, str]:
        """Вернуть стабильные метаданные координат для проверки совместимости кэша."""
        return {
            "latitude": cls._round_float(latitude, 6),
            "longitude": cls._round_float(longitude, 6),
            "altitude": cls._round_float(altitude, 1),
        }

    @staticmethod
    def _round_float(value: Any, digits: int) -> str:
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "unknown"

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


async def async_remove_entry_cache(
    hass: HomeAssistant,
    entry_id: str,
    *,
    entry_title: str | None = None,
) -> None:
    """Удалить файл постоянного кэша ConfigEntry по entry_id.

    Используется, когда Home Assistant удаляет ConfigEntry, но runtime-helper
    SilamPollenCacheStore уже недоступен.
    """
    log_prefix = f"[{entry_title or entry_id}]"
    store: Store[dict[str, Any]] = Store(
        hass,
        CACHE_STORAGE_VERSION,
        _cache_storage_key(entry_id),
    )
    try:
        await store.async_remove()
    except Exception as err:  # noqa: BLE001 - очистка не должна ломать удаление записи
        _LOGGER.warning(
            "%s Failed to remove persistent cache file: %s",
            log_prefix,
            err,
        )
        return
    _LOGGER.debug("%s Persistent cache file removed", log_prefix)

