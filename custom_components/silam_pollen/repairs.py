"""Repair helpers for SILAM Pollen."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DATASETS, DOMAIN

ISSUE_MANUAL_DATASET_UNAVAILABLE = "manual_dataset_unavailable"


def _manual_dataset_issue_id(entry_id: str) -> str:
    """Вернуть стабильный issue_id для конкретной записи ConfigEntry."""
    return f"{ISSUE_MANUAL_DATASET_UNAVAILABLE}_{entry_id}"


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
