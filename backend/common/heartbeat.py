"""Heartbeat helper for long-running services without HTTP endpoints.

Writes a sentinel file at a fixed cadence so container orchestrators (Docker
HEALTHCHECK) can distinguish a live event loop from a hung process.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

HEARTBEAT_PATH = Path(os.environ.get("HEARTBEAT_PATH", "/tmp/heartbeat"))  # noqa: S108
_DEFAULT_INTERVAL_SECONDS = 30


def touch_heartbeat(path: Path = HEARTBEAT_PATH) -> None:
    """Bump the heartbeat file's mtime; create it if missing."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        os.utime(path, None)
    except OSError as exc:
        logger.warning("heartbeat_touch_failed", path=str(path), error=str(exc))


async def run_heartbeat(
    stop_event: asyncio.Event,
    *,
    interval_seconds: int = _DEFAULT_INTERVAL_SECONDS,
    path: Path = HEARTBEAT_PATH,
) -> None:
    """Periodically refresh the heartbeat file until stop_event is set."""
    touch_heartbeat(path)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            touch_heartbeat(path)
