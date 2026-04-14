"""Heartbeat helper unit tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from backend.common.heartbeat import run_heartbeat, touch_heartbeat


class TestTouchHeartbeat:
    def test_creates_missing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "hb"
        assert not target.exists()
        touch_heartbeat(target)
        assert target.exists()

    def test_refreshes_mtime(self, tmp_path: Path) -> None:
        target = tmp_path / "hb"
        touch_heartbeat(target)
        first = target.stat().st_mtime
        import os

        os.utime(target, (first - 100, first - 100))
        touch_heartbeat(target)
        assert target.stat().st_mtime > first - 100


@pytest.mark.asyncio
async def test_run_heartbeat_refreshes_until_stop(tmp_path: Path) -> None:
    target = tmp_path / "hb"
    stop = asyncio.Event()
    task = asyncio.create_task(run_heartbeat(stop, interval_seconds=1, path=target))
    await asyncio.sleep(2.2)
    assert target.exists()
    mtime1 = target.stat().st_mtime
    await asyncio.sleep(1.2)
    mtime2 = target.stat().st_mtime
    assert mtime2 > mtime1
    stop.set()
    await task


@pytest.mark.asyncio
async def test_run_heartbeat_stops_on_event(tmp_path: Path) -> None:
    target = tmp_path / "hb"
    stop = asyncio.Event()
    task = asyncio.create_task(run_heartbeat(stop, interval_seconds=5, path=target))
    await asyncio.sleep(0.1)
    stop.set()
    await asyncio.wait_for(task, timeout=1.0)
