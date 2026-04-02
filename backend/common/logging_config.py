"""Centralized logging configuration with file rotation. (RULE 06, 10)"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog
import structlog.stdlib

# Log directory — configurable via env, default ./logs
LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 10


def setup_logging(service_name: str) -> None:
    """Configure structlog + stdlib logging with rotating file handlers.

    Args:
        service_name: One of 'api', 'crawler', 'processor'.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Root logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler (JSON)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Service-specific rotating file handler
    service_handler = RotatingFileHandler(
        LOG_DIR / f"{service_name}.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    service_handler.setLevel(logging.INFO)
    root_logger.addHandler(service_handler)

    # Error-only rotating file handler
    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # structlog configuration
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
