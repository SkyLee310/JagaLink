"""Alerts (F4–F6) as the API returns them and the stream pushes them (D-36)."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.db.models import ActionKind, AlertStatus, Role, TriageStatus
from app.engine.rules import RuleKey, Severity
from app.schemas.common import ApiDatetime


class UserRef(BaseModel):
    id: UUID
    code: str
    name: str
    role: Role


class NextNodeBasis(BaseModel):
    """Why this camera comes next (D-20, D-57): the walk and distance from the alert's node, the
    share of normal routes that take this step, and how well it keeps the direction of travel."""

    walk_s: float
    distance_m: float | None
    transition_share: float
    direction: float
    backtrack: bool
    score: float


class NextNodeOut(BaseModel):
    id: UUID
    basis: NextNodeBasis


class AlertActionOut(BaseModel):
    id: UUID
    action: ActionKind
    reason: str
    ts: ApiDatetime
    """The run's clock when the guard acted (event time, D-31)."""
    user: UserRef


class AlertOut(BaseModel):
    """One alert: a rule matching one anonymous path (D-18), the guard it went to and the
    camera to check next (F5). Keep the copy with the highest `version`: the stream may deliver
    an older one after a newer one."""

    id: UUID
    run_id: UUID
    version: int
    status: AlertStatus
    rule: RuleKey
    rule_name: str
    detail: str
    """Why the rule matched, in words."""
    score: float | None
    """Loitering: the seconds counted in the zone."""
    track_id: UUID | None
    """None once the path has expired (D-56); the alert keeps its evidence."""
    track_anon_id: str | None
    node_id: UUID
    """Where the rule last matched: the alert's location."""
    severity: Severity
    severity_reason: str
    triage_status: TriageStatus
    """`pending` while the severity is the provisional rule-based one (D-60, D-61)."""
    assigned_user: UserRef | None
    """The nearest on-duty guard, or the supervisor when the alert escalated (D-19)."""
    walk_s: float | None
    """The assigned guard's walking time to the alert's node; None when escalated."""
    next_node: NextNodeOut | None
    evidence_event_ids: list[UUID]
    created_ts: ApiDatetime
    """When the rule first matched (event time)."""
    updated_ts: ApiDatetime
    acked_ts: ApiDatetime | None
    """When a guard confirmed or dismissed it (the run's clock)."""
    actions: list[AlertActionOut]


OneLine = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=200, pattern=r"^[^\r\n]*$")
]


class AlertActionIn(BaseModel):
    """Confirm or dismiss, with an optional one-line reason (F6)."""

    action: ActionKind
    reason: OneLine = ""
