"""The event contract's vocabulary (D-16), shared by the scripts, the database and the engine."""

from typing import Literal

EventType = Literal["appear", "dwell", "disappear"]
ObjectClass = Literal["person", "vehicle"]
EventSource = Literal["sim", "video"]
