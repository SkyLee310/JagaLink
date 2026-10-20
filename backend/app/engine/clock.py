"""The simulated clock (D-31): event time that runs `speed` times faster than the wall clock.

Pure: every method takes the current wall time (monotonic seconds) instead of reading it, so the
player and its tests decide what "now" is.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SimClock:
    position: datetime
    """Simulated time at the wall moment `anchor`."""
    anchor: float
    speed: float
    playing: bool = False

    def now(self, wall: float) -> datetime:
        if not self.playing:
            return self.position
        return self.position + timedelta(seconds=(wall - self.anchor) * self.speed)

    def play(self, wall: float) -> None:
        self.position, self.anchor, self.playing = self.now(wall), wall, True

    def pause(self, wall: float) -> None:
        self.position, self.anchor, self.playing = self.now(wall), wall, False

    def set_speed(self, speed: float, wall: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be above 0")
        self.position, self.anchor, self.speed = self.now(wall), wall, speed

    def seek(self, position: datetime, wall: float) -> None:
        self.position, self.anchor = position, wall

    def wall_until(self, moment: datetime, wall: float) -> float:
        """Wall seconds until the clock reaches `moment`: 0 if it has, infinity while paused."""
        ahead = (moment - self.now(wall)).total_seconds()
        if ahead <= 0:
            return 0.0
        return ahead / self.speed if self.playing else math.inf
