"""The player (F2): emits a run's events when the simulated clock reaches them (D-31).

An asyncio task inside the API process (D-77). It owns no I/O: `emit` stores and publishes each
batch. Pause, resume and a new speed act through the clock and wake the task; a batch already
being emitted always finishes first.
"""

import asyncio
import contextlib
import math
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Protocol

from app.engine.clock import SimClock
from app.sim.script import ScriptEvent

BATCH_SIZE = 200


class Timer(Protocol):
    """Wall time for the player; tests swap in one that never waits."""

    def now(self) -> float: ...

    async def sleep(self, seconds: float, wake: asyncio.Event) -> None:
        """Wait this long (forever when infinite), or until `wake` is set."""
        ...


class WallTimer:
    def now(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float, wake: asyncio.Event) -> None:
        timeout = None if math.isinf(seconds) else max(seconds, 0.0)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(wake.wait(), timeout)


Emit = Callable[[list[ScriptEvent]], Awaitable[None]]


class Player:
    def __init__(
        self,
        events: Sequence[ScriptEvent],
        clock: SimClock,
        end: datetime,
        timer: Timer,
        emit: Emit,
        start_index: int = 0,
    ) -> None:
        self.events = events
        self.index = start_index
        self.clock = clock
        self.end = end
        self.timer = timer
        self.emit = emit
        self.wake = asyncio.Event()
        self.stopping = False
        self.done = False
        """True once every event is out and the clock has reached the end of the window."""

    def position(self) -> datetime:
        return min(self.clock.now(self.timer.now()), self.end)

    async def run(self) -> bool:
        """Play to the end of the window (True), or until `stop` (False)."""
        while not self.stopping:
            wall = self.timer.now()
            moment = self.clock.now(wall)
            due: list[ScriptEvent] = []
            for event in self.events[self.index : self.index + BATCH_SIZE]:
                if event.ts > moment:
                    break
                due.append(event)
            if due:
                await self.emit(due)
                self.index += len(due)
                continue
            if self.index >= len(self.events) and moment >= self.end:
                self.done = True
                return True
            target = self.events[self.index].ts if self.index < len(self.events) else self.end
            self.wake.clear()
            await self.timer.sleep(self.clock.wall_until(target, wall), self.wake)
        return False

    def pause(self) -> None:
        self.clock.pause(self.timer.now())
        self.wake.set()

    def resume(self, speed: float | None = None) -> None:
        wall = self.timer.now()
        if speed is not None:
            self.clock.set_speed(speed, wall)
        self.clock.play(wall)
        self.wake.set()

    def stop(self) -> None:
        self.stopping = True
        self.wake.set()
