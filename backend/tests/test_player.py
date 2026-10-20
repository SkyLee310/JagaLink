"""M2.2: the player emits each event when the simulated clock reaches it, and obeys its controls."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app.engine.clock import SimClock
from app.sim.golden import seeded_scripts
from app.sim.player import Player
from app.sim.script import ScriptEvent
from tests.fakes import InstantTimer


@pytest.fixture(scope="module")
def live() -> list[ScriptEvent]:
    return seeded_scripts()["s2-night-fence"].live_events()


@pytest.fixture(scope="module")
def window() -> tuple[datetime, datetime]:
    script = seeded_scripts()["s2-night-fence"]
    return script.window_start, script.window_end


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[ScriptEvent]] = []

    async def __call__(self, batch: list[ScriptEvent]) -> None:
        self.batches.append(batch)

    @property
    def events(self) -> list[ScriptEvent]:
        return [event for batch in self.batches for event in batch]


def test_plays_every_event_in_order_then_finishes(
    live: list[ScriptEvent], window: tuple[datetime, datetime]
) -> None:
    recorder = Recorder()
    player = Player(live, SimClock(window[0], 0.0, 10), window[1], InstantTimer(), recorder)
    player.resume()

    finished = asyncio.run(player.run())

    assert finished and player.done
    assert recorder.events == live
    assert player.position() == window[1]


def test_each_event_waits_for_its_simulated_time(
    live: list[ScriptEvent], window: tuple[datetime, datetime]
) -> None:
    timer = InstantTimer()
    clock = SimClock(window[0], 0.0, 10)
    seen: list[tuple[datetime, datetime]] = []

    async def emit(batch: list[ScriptEvent]) -> None:
        seen.extend((event.ts, clock.now(timer.now())) for event in batch)

    player = Player(live, clock, window[1], timer, emit)
    player.resume()
    asyncio.run(player.run())

    # Never early, and never later than the clock reached when it was due.
    assert all(ts <= at < ts + timedelta(milliseconds=1) for ts, at in seen)


class ManualTimer:
    """Wall time moves only when the test moves it."""

    def __init__(self) -> None:
        self.wall = 0.0

    def now(self) -> float:
        return self.wall

    async def sleep(self, seconds: float, wake: asyncio.Event) -> None:
        await wake.wait()


async def settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


def test_pause_holds_resume_continues_and_stop_ends(
    live: list[ScriptEvent], window: tuple[datetime, datetime]
) -> None:
    def due(clock: SimClock, timer: ManualTimer) -> int:
        return sum(1 for event in live if event.ts <= clock.now(timer.now()))

    async def scenario() -> tuple[list[tuple[int, int]], bool]:
        recorder, timer = Recorder(), ManualTimer()
        clock = SimClock(window[0], 0.0, 10)
        player = Player(live, clock, window[1], timer, recorder)
        player.resume()
        task = asyncio.create_task(player.run())
        counts: list[tuple[int, int]] = []

        async def advance(seconds: float) -> None:
            timer.wall += seconds
            player.wake.set()
            await settle()
            counts.append((len(recorder.events), due(clock, timer)))

        await advance((live[2].ts - window[0]).total_seconds() / 10)
        player.pause()
        await advance(1000)
        player.resume()
        await advance((live[5].ts - live[2].ts).total_seconds() / 10)
        player.stop()
        return counts, await task

    counts, finished = asyncio.run(scenario())
    played, paused, resumed = counts
    assert played[0] == played[1] >= 3
    assert paused == played  # a thousand wall seconds later, still nothing new
    assert resumed[0] == resumed[1] >= 6
    assert finished is False


def test_a_new_speed_shortens_the_wait(
    live: list[ScriptEvent], window: tuple[datetime, datetime]
) -> None:
    timer = InstantTimer()
    player = Player(live, SimClock(window[0], 0.0, 10), window[1], timer, Recorder())
    player.resume(speed=60)
    asyncio.run(player.run())
    assert timer.wall == pytest.approx((window[1] - window[0]).total_seconds() / 60)


def test_starts_after_the_events_already_stored(
    live: list[ScriptEvent], window: tuple[datetime, datetime]
) -> None:
    recorder = Recorder()
    clock = SimClock(live[4].ts, 0.0, 10)
    player = Player(live, clock, window[1], InstantTimer(), recorder, start_index=5)
    player.resume()
    asyncio.run(player.run())
    assert recorder.events == live[5:]
