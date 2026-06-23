"""Compatibility shim для старого импорта runs_catalog.py.

Основная реализация catalog-слоя перенесена в silam_catalog.py.
Этот файл временно оставлен, чтобы старые импорты из .runs_catalog
не ломали hot-reload, тесты или внешние ссылки внутри кастомной интеграции.
"""

from __future__ import annotations

from .silam_catalog import (
    LatestRunInfo,
    RootCatalogInfo,
    RootCatalogManager,
    RunsCatalogManager,
    SilamCatalogManager,
)

__all__ = [
    "LatestRunInfo",
    "RootCatalogInfo",
    "RootCatalogManager",
    "RunsCatalogManager",
    "SilamCatalogManager",
]
