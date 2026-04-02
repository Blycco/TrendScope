"""Tests for centralized logging configuration with file rotation."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import structlog


def test_setup_logging_creates_log_directory(tmp_path: Path) -> None:
    """setup_logging should create LOG_DIR if it does not exist."""
    log_dir = tmp_path / "test_logs"
    assert not log_dir.exists()

    with patch.dict(os.environ, {"LOG_DIR": str(log_dir)}):
        import importlib

        import backend.common.logging_config as lc

        importlib.reload(lc)
        lc.setup_logging("api")

    assert log_dir.exists()


def test_setup_logging_adds_rotating_file_handlers(tmp_path: Path) -> None:
    """setup_logging should attach RotatingFileHandlers to the root logger."""
    # Reset root logger handlers to isolate test
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
            import importlib

            import backend.common.logging_config as lc

            importlib.reload(lc)
            lc.setup_logging("crawler")

        rotating_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating_handlers) == 2
    finally:
        root_logger.handlers = original_handlers


def test_setup_logging_service_log_file(tmp_path: Path) -> None:
    """Service-specific log file should be named after the service."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
            import importlib

            import backend.common.logging_config as lc

            importlib.reload(lc)
            lc.setup_logging("processor")

        file_paths = [
            Path(h.baseFilename) for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
        ]
        names = {p.name for p in file_paths}
        assert "processor.log" in names
        assert "error.log" in names
    finally:
        root_logger.handlers = original_handlers


def test_error_handler_level(tmp_path: Path) -> None:
    """error.log handler should only capture ERROR and above."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
            import importlib

            import backend.common.logging_config as lc

            importlib.reload(lc)
            lc.setup_logging("api")

        error_handler = next(
            h
            for h in root_logger.handlers
            if isinstance(h, RotatingFileHandler) and Path(h.baseFilename).name == "error.log"
        )
        assert error_handler.level == logging.ERROR
    finally:
        root_logger.handlers = original_handlers


def test_service_handler_level(tmp_path: Path) -> None:
    """Service log handler should capture INFO and above."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
            import importlib

            import backend.common.logging_config as lc

            importlib.reload(lc)
            lc.setup_logging("api")

        service_handler = next(
            h
            for h in root_logger.handlers
            if isinstance(h, RotatingFileHandler) and Path(h.baseFilename).name == "api.log"
        )
        assert service_handler.level == logging.INFO
    finally:
        root_logger.handlers = original_handlers


def test_rotating_handler_max_bytes(tmp_path: Path) -> None:
    """Rotating handlers should have 10 MB max bytes configured."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
            import importlib

            import backend.common.logging_config as lc

            importlib.reload(lc)
            lc.setup_logging("api")

        for handler in root_logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                assert handler.maxBytes == 10 * 1024 * 1024
                assert handler.backupCount == 10
    finally:
        root_logger.handlers = original_handlers


def test_setup_logging_configures_structlog(tmp_path: Path) -> None:
    """setup_logging should configure structlog without raising."""
    with patch.dict(os.environ, {"LOG_DIR": str(tmp_path)}):
        import importlib

        import backend.common.logging_config as lc

        importlib.reload(lc)
        # Should not raise
        lc.setup_logging("api")

    logger = structlog.get_logger("test")
    assert logger is not None


def test_log_dir_uses_env_variable(tmp_path: Path) -> None:
    """LOG_DIR env variable should control where logs are written."""
    custom_dir = tmp_path / "custom_log_dir"

    with patch.dict(os.environ, {"LOG_DIR": str(custom_dir)}):
        import importlib

        import backend.common.logging_config as lc

        importlib.reload(lc)
        lc.setup_logging("api")

    assert custom_dir.exists()
