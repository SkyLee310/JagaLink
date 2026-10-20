"""Scenarios and their runs (F2). Nothing here carries the ground truth (D-70)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import RunMode, RunState
from app.schemas.common import ApiDatetime


class ScenarioOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str
    duration_s: int
    """Length of the live window the player plays."""
    default_speed: float
    window_start: ApiDatetime
    window_end: ApiDatetime


class RunCreate(BaseModel):
    """Start a live run; it stops the community's previous one (D-77)."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: UUID
    speed: float | None = Field(default=None, gt=0, le=120)
    """Simulated seconds per wall second; the scenario's default when left out."""
    mode: Literal["live"] = "live"


class RunResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed: float | None = Field(default=None, gt=0, le=120)


class RunOut(BaseModel):
    id: UUID
    scenario_id: UUID
    scenario_code: str
    scenario_name: str
    mode: RunMode
    speed: float
    state: RunState
    started_at: ApiDatetime | None
    window_start: ApiDatetime
    window_end: ApiDatetime
    clock: ApiDatetime
    """Simulated time the run has reached."""
    events_emitted: int
    events_total: int
