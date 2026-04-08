"""SSE endpoint for real-time trend updates."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.processor.shared.cache_manager import get_pubsub_redis

router = APIRouter(prefix="/live", tags=["live"])
logger = structlog.get_logger(__name__)

_HEARTBEAT_INTERVAL = 30
_CHANNEL = "trends:new"


async def _event_generator() -> AsyncGenerator[str, None]:
    """Yield SSE events from Redis pub/sub, with keep-alive heartbeats."""
    redis = get_pubsub_redis()
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(_CHANNEL)
        logger.info("sse_client_connected")
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=float(_HEARTBEAT_INTERVAL),
                )
                if message and message.get("type") == "message":
                    group_id = message["data"]
                    yield f"data: {group_id}\n\n"
                else:
                    yield ": keep-alive\n\n"
            except TimeoutError:
                yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                break
    except Exception as exc:
        logger.warning("sse_generator_error", error=str(exc))
    finally:
        try:
            await pubsub.unsubscribe(_CHANNEL)
            await pubsub.aclose()
        except Exception as cleanup_exc:
            logger.debug("sse_cleanup_error", error=str(cleanup_exc))
        logger.info("sse_client_disconnected")


@router.get("/trends")
async def live_trends() -> StreamingResponse:
    """SSE endpoint: stream new trend group_ids as they are saved."""
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
