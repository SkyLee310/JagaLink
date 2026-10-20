"""The live stream (D-36): `GET /stream?run_id=` as Server-Sent Events.

The browser reads it with a fetch-based client so it can send the bearer token. A client first
gets the run's backlog, then each message as it is published; a comment line every 15 s keeps
idle connections open. The stream ends when the run is reset or replaced, and the client
reconnects to start afresh.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.core.auth import Claims, current_claims
from app.core.errors import ApiError
from app.core.hub import Hub, Message
from app.routers.scenarios import Runs
from app.schemas.common import error_responses

router = APIRouter(tags=["stream"])

PING_S = 15.0


async def frames(
    hub: Hub,
    run_id: UUID,
    backlog: list[Message],
    queue: asyncio.Queue[Message | None],
    ping_s: float = PING_S,
) -> AsyncIterator[str]:
    try:
        for message in backlog:
            yield message.frame()
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), ping_s)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if message is None:
                return
            yield message.frame()
    finally:
        hub.unsubscribe(run_id, queue)


@router.get(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, **error_responses(401, 404, 422)},
)
async def stream(
    run_id: UUID, claims: Annotated[Claims, Depends(current_claims)], runs: Runs
) -> StreamingResponse:
    """Messages `event`, `track_update`, `alert`, `alert_update` and `timeline_ready` for a run."""
    channel = runs.hub.channel(run_id)
    if channel is None:
        # The token is enough to check the community; the backlog read uses its own session,
        # so no database connection stays open for the life of the stream.
        backlog = await run_in_threadpool(runs.backlog, run_id, claims.community_id)
        channel = runs.hub.open(run_id, claims.community_id, backlog)
    if channel.community_id != claims.community_id:
        raise ApiError(404, "run_not_found", "No run in your community has that ID")
    backlog_messages, queue = runs.hub.subscribe(run_id)
    return StreamingResponse(
        frames(runs.hub, run_id, backlog_messages, queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
