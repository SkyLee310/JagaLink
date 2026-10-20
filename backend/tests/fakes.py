"""Timers for the player in tests: one that never waits, one that never moves."""

import asyncio
import math


class InstantTimer:
    """Wall time jumps straight to whatever the player waits for."""

    def __init__(self) -> None:
        self.wall = 0.0

    def now(self) -> float:
        return self.wall

    async def sleep(self, seconds: float, wake: asyncio.Event) -> None:
        if math.isinf(seconds):
            await wake.wait()
            return
        self.wall += max(seconds, 0.0)
        await asyncio.sleep(0)


class FrozenTimer:
    """Wall time stands still: a player emits nothing until a test moves the clock itself."""

    def now(self) -> float:
        return 0.0

    async def sleep(self, seconds: float, wake: asyncio.Event) -> None:
        await wake.wait()
