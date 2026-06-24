"""Repair helpers for SILAM Pollen."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import DATASETS, DOMAIN

ISSUE_MANUAL_DATASET_UNAVAILABLE = "manual_dataset_unavailable"
ISSUE_LEGACY_INDEX_SENSOR_DEPRECATED = "legacy_index_sensor_deprecated"


def _manual_dataset_issue_id(entry_id: str) -> str:
    """Вернуть стабильный issue_id для конкретной записи ConfigEntry."""
    return f"{ISSUE_MANUAL_DATASET_UNAVAILABLE}_{entry_id}"


def _legacy_index_sensor_issue_id(entry_id: str) -> str:
    """Вернуть стабильный issue_id для устаревшего index-сенсора."""
    return f"{ISSUE_LEGACY_INDEX_SENSOR_DEPRECATED}_{entry_id}"


def _legacy_index_unique_id(entry_id: str) -> str:
    """Вернуть unique_id устаревшего index-сенсора."""
    return f"{entry_id}_index"


def _find_legacy_index_entity_id(hass: HomeAssistant, entry_id: str) -> str | None:
    """Найти entity_id устаревшего index-сенсора в entity registry."""
    registry = er.async_get(hass)
    legacy_unique_id = _legacy_index_unique_id(entry_id)

    entity_id = registry.async_get_entity_id("sensor", DOMAIN, legacy_unique_id)
    if entity_id is not None:
        entity_entry = registry.async_get(entity_id)
        if (
            entity_entry is not None
            and entity_entry.config_entry_id == entry_id
            and getattr(entity_entry, "disabled_by", None) is None
        ):
            return entity_id

    # Защитный fallback на случай, если platform/unique_id были записаны иначе
    # в старой версии Home Assistant или при ручных переносах registry.
    for entity_entry in registry.entities.values():
        if (
            entity_entry.config_entry_id == entry_id
            and entity_entry.domain == "sensor"
            and entity_entry.unique_id == legacy_unique_id
            and getattr(entity_entry, "disabled_by", None) is None
        ):
            return entity_entry.entity_id

    return None


def _dataset_label(dataset_name: str | None) -> str:
    """Вернуть человекочитаемое имя датасета для Repair issue."""
    if not dataset_name:
        return "unknown"

    meta = DATASETS.get(dataset_name)
    if meta is not None and meta.label:
        return meta.label

    return dataset_name


async def async_create_manual_dataset_unavailable_issue(
    hass: HomeAssistant,
    *,
    entry_id: str | None,
    entry_title: str | None,
    dataset_name: str | None,
) -> None:
    """Создать Repair issue для ручного датасета, удалённого из root catalog."""
    if not entry_id:
        return

    dataset_name = dataset_name or "unknown"
    dataset_label = _dataset_label(dataset_name)

    ir.async_create_issue(
        hass,
        DOMAIN,
        _manual_dataset_issue_id(entry_id),
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_MANUAL_DATASET_UNAVAILABLE,
        translation_placeholders={
            "entry_title": entry_title or entry_id,
            "dataset_name": dataset_name,
            "dataset_label": dataset_label,
        },
        data={
            "entry_id": entry_id,
            "entry_title": entry_title,
            "dataset_name": dataset_name,
            "dataset_label": dataset_label,
        },
    )


async def async_delete_manual_dataset_unavailable_issue(
    hass: HomeAssistant,
    *,
    entry_id: str | None,
) -> None:
    """Удалить Repair issue ручного датасета, если проблема больше не актуальна."""
    if not entry_id:
        return

    ir.async_delete_issue(
        hass,
        DOMAIN,
        _manual_dataset_issue_id(entry_id),
    )


async def async_create_legacy_index_sensor_deprecated_issue(
    hass: HomeAssistant,
    *,
    entry_id: str | None,
    entry_title: str | None,
    entity_id: str | None,
) -> None:
    """Создать Repair issue для устаревшего index-сенсора."""
    if not entry_id or not entity_id:
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        _legacy_index_sensor_issue_id(entry_id),
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_INDEX_SENSOR_DEPRECATED,
        translation_placeholders={
            "entry_title": entry_title or entry_id,
            "entity_id": entity_id,
        },
        data={
            "entry_id": entry_id,
            "entry_title": entry_title,
            "entity_id": entity_id,
        },
    )


async def async_delete_legacy_index_sensor_deprecated_issue(
    hass: HomeAssistant,
    *,
    entry_id: str | None,
) -> None:
    """Удалить Repair issue устаревшего index-сенсора."""
    if not entry_id:
        return

    ir.async_delete_issue(
        hass,
        DOMAIN,
        _legacy_index_sensor_issue_id(entry_id),
    )


async def async_update_legacy_index_sensor_deprecated_issue(
    hass: HomeAssistant,
    *,
    entry_id: str | None,
    entry_title: str | None,
) -> None:
    """Создать или удалить Repair issue по фактическому наличию legacy index-сенсора."""
    if not entry_id:
        return

    entity_id = _find_legacy_index_entity_id(hass, entry_id)
    if entity_id is None:
        await async_delete_legacy_index_sensor_deprecated_issue(hass, entry_id=entry_id)
        return

    await async_create_legacy_index_sensor_deprecated_issue(
        hass,
        entry_id=entry_id,
        entry_title=entry_title,
        entity_id=entity_id,
    )
