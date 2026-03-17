"""Tests for common/paths.py."""

from __future__ import annotations

from pathlib import Path

from backend.common.paths import (
    BACKEND_DIR,
    BASE_DIR,
    LOG_DIR,
    MIGRATIONS_DIR,
    STATIC_DIR,
)


def test_base_dir_is_path() -> None:
    assert isinstance(BASE_DIR, Path)


def test_backend_dir_under_base() -> None:
    assert BACKEND_DIR == BASE_DIR / "backend"


def test_migrations_dir_under_base() -> None:
    assert MIGRATIONS_DIR == BASE_DIR / "migrations"


def test_log_dir_under_base() -> None:
    assert LOG_DIR == BASE_DIR / "logs"


def test_static_dir_under_base() -> None:
    assert STATIC_DIR == BASE_DIR / "static"
