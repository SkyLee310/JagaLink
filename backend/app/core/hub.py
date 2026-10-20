"""In-memory fan-out of each run's live messages to its SSE subscribers (D-36, D-77).

A run's channel keeps every message published so far, so a client that connects late or
reconnects first gets the whole backlog, then the live messages. A channel starts from the
database's backlog for the run, so it survives a restart. Everything here runs on the app's event
loop; other threads publish through `publish_threadsafe`.
"""

import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

MessageType = str
"""event, track_update, alert, alert_update or timeline_ready (D-36)."""
Item = tuple[MessageType, dict[str, Any]]


@dataclass(frozen=True)
class Message:
    id: int
    type: MessageType
    data: dict[str, Any]

    def frame(self) -> str:
        data = json.dumps(self.data, separators=(",", ":"))
        return f"id: {self.id}\nevent: {self.type}\ndata: {data}\n\n"


@dataclass
class Channel:
    community_id: UUID
    log: list[Message] = field(default_factory=list)
    queues: set[asyncio.Queue[Message | None]] = field(default_factory=set)

    def append(self, items: Iterable[Item]) -> list[Message]:
        added = [
            Message(len(self.log) + number, kind, data)
            for number, (kind, data) in enumerate(items, start=1)
        ]
        self.log += added
        return added


class Hub:
    def __init__(self) -> None:
        self.channels: dict[UUID, Channel] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def channel(self, run_id: UUID) -> Channel | None:
        return self.channels.get(run_id)

    def open(self, run_id: UUID, community_id: UUID, backlog: Iterable[Item] = ()) -> Channel:
        """The run's channel; a new one starts from `backlog`, an existing one stays as it is."""
        channel = self.channels.get(run_id)
        if channel is None:
            channel = self.channels[run_id] = Channel(community_id)
            channel.append(backlog)
        return channel

    def publish(self, run_id: UUID, items: Iterable[Item]) -> None:
        """Log the messages and hand them to every subscriber of the run.

        A run nobody has opened is skipped: whoever opens it later reads the backlog from the
        database, which already holds what these messages describe.
        """
        channel = self.channels.get(run_id)
        if channel is None:
            return
        for message in channel.append(items):
            for queue in channel.queues:
                queue.put_nowait(message)

    def publish_threadsafe(self, run_id: UUID, items: Iterable[Item]) -> None:
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.publish, run_id, list(items))

    def subscribe(self, run_id: UUID) -> tuple[list[Message], asyncio.Queue[Message | None]]:
        """The backlog so far, and a queue that receives every later message (None: closed)."""
        channel = self.channels[run_id]
        queue: asyncio.Queue[Message | None] = asyncio.Queue()
        channel.queues.add(queue)
        return list(channel.log), queue

    def unsubscribe(self, run_id: UUID, queue: asyncio.Queue[Message | None]) -> None:
        channel = self.channels.get(run_id)
        if channel is not None:
            channel.queues.discard(queue)

    def close(self, run_id: UUID) -> None:
        """End every subscriber's stream and drop the log; the next client starts afresh."""
        channel = self.channels.pop(run_id, None)
        if channel is not None:
            for queue in channel.queues:
                queue.put_nowait(None)
