"""M2.2: the simulated clock runs event time at the chosen speed (D-31)."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from app.engine.clock import SimClock

START = datetime(2026, 10, 21, 11, 18, tzinfo=UTC)


def test_a_paused_clock_stands_still() -> None:
    clock = SimClock(START, anchor=100.0, speed=10)
    assert clock.now(500.0) == START
    assert clock.wall_until(START + timedelta(seconds=5), 500.0) == math.inf


def test_playing_runs_speed_times_faster() -> None:
    clock = SimClock(START, anchor=0.0, speed=10)
    clock.play(100.0)
    assert clock.now(103.5) == START + timedelta(seconds=35)
    assert clock.wall_until(START + timedelta(seconds=50), 103.5) == pytest.approx(1.5)
    assert clock.wall_until(START, 103.5) == 0


def test_pause_keeps_the_position_and_resume_continues_from_it() -> None:
    clock = SimClock(START, anchor=0.0, speed=10)
    clock.play(0.0)
    clock.pause(2.0)
    assert clock.now(60.0) == START + timedelta(seconds=20)
    clock.play(60.0)
    assert clock.now(61.0) == START + timedelta(seconds=30)


def test_a_new_speed_applies_from_now_on() -> None:
    clock = SimClock(START, anchor=0.0, speed=10)
    clock.play(0.0)
    clock.set_speed(60, 1.0)
    assert clock.now(2.0) == START + timedelta(seconds=70)
    with pytest.raises(ValueError):
        clock.set_speed(0, 2.0)


def test_seek_moves_the_position() -> None:
    clock = SimClock(START, anchor=0.0, speed=10)
    clock.play(0.0)
    clock.seek(START + timedelta(minutes=5), 3.0)
    assert clock.now(4.0) == START + timedelta(minutes=5, seconds=10)
