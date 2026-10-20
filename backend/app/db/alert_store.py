"""Stores and reads alerts (F4–F6): one anomaly row and one alert row per (track, rule) (D-59).
The caller commits.

Their IDs come from the run, the linker's track number and the rule, so a pipeline rebuilt after a
restart lands on the same rows. The pipeline writes what the engine decides; a guard's action
writes the status. Both lock the alert's row first and bump its `version`.
"""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.hub import Item, MessageType
from app.db import track_store
from app.db.models import ActionKind, Alert, AlertAction, AlertStatus, Anomaly, AppUser, Track
from app.engine.alerting import AlertChange, AlertState
from app.engine.router import Suggestion
from app.engine.rules import RULE_NAMES, RuleKey
from app.schemas.alerts import AlertActionOut, AlertOut, NextNodeBasis, NextNodeOut, UserRef

HANDLED: frozenset[AlertStatus] = frozenset({"acked", "dismissed"})
"""A guard has confirmed or dismissed it; later matches still add evidence (D-59)."""


def anomaly_id(run_id: uuid.UUID, track: int, rule: RuleKey) -> uuid.UUID:
    return uuid.uuid5(run_id, f"anomaly-{track}-{rule}")


def alert_id(run_id: uuid.UUID, track: int, rule: RuleKey) -> uuid.UUID:
    return uuid.uuid5(run_id, f"alert-{track}-{rule}")


@dataclass(frozen=True)
class Staff:
    """Who alerts go to: user IDs by code, and the supervisor an alert escalates to (D-19)."""

    user_ids: Mapping[str, uuid.UUID]
    supervisor: uuid.UUID | None


def save(
    db: Session,
    community_id: uuid.UUID,
    run_id: uuid.UUID,
    changes: Sequence[AlertChange],
    node_ids: Mapping[str, uuid.UUID],
    staff: Staff,
) -> list[Item]:
    """Write the alerts a batch opened or changed; their stream messages, in order (D-36).

    A change for a row that already exists updates it, even one a rebuilt pipeline reports as
    new. The path's ID is set once, when its alert opens: the track was written just before.
    """
    latest: dict[tuple[int, RuleKey], AlertChange] = {}
    for change in changes:
        key = (change.alert.track, change.alert.rule)
        opened = change.kind == "alert" or (key in latest and latest[key].kind == "alert")
        latest[key] = AlertChange("alert" if opened else "alert_update", change.alert)
    kinds: dict[uuid.UUID, MessageType] = {}
    for change in latest.values():
        state = change.alert
        anomaly = db.get(Anomaly, anomaly_id(run_id, state.track, state.rule))
        if anomaly is None:
            anomaly = Anomaly(
                id=anomaly_id(run_id, state.track, state.rule),
                community_id=community_id,
                run_id=run_id,
                track_id=track_store.track_id(run_id, state.track),
                track_number=state.track,
                rule_key=state.rule,
                ts=state.first_ts,
            )
            db.add(anomaly)
        anomaly.last_ts, anomaly.node_id = state.last_ts, node_ids[state.node]
        anomaly.evidence_event_ids = [uuid.UUID(event_id) for event_id in state.evidence]
        anomaly.score, anomaly.detail = state.score, state.detail

        alert = _locked(db, alert_id(run_id, state.track, state.rule))
        if alert is None:
            alert = _open(db, community_id, run_id, anomaly.id, state, staff)
            kinds[alert.id] = "alert"
        else:
            kinds[alert.id] = "alert_update"
        alert.version += 1
        if alert.triage_status != "agent":
            alert.severity, alert.severity_reason = state.severity, state.severity_reason
        suggestion = state.next_camera
        alert.next_node_id = node_ids[suggestion.node] if suggestion else None
        alert.next_node_basis = _basis(suggestion) if suggestion else None
        alert.updated_ts = max(alert.updated_ts, state.updated_ts)
    db.flush()
    outs = {out.id: out for out in load(db, _alerts().where(Alert.id.in_(kinds)))}
    return [alert_message(kind, outs[id_]) for id_, kind in kinds.items()]


def _locked(db: Session, id_: uuid.UUID) -> Alert | None:
    return db.get(Alert, id_, with_for_update=True, populate_existing=True)


def _open(
    db: Session,
    community_id: uuid.UUID,
    run_id: uuid.UUID,
    anomaly: uuid.UUID,
    state: AlertState,
    staff: Staff,
) -> Alert:
    """A new alert goes to the nearest on-duty guard; with none, to the supervisor (D-19)."""
    escalated = state.guard is None
    alert = Alert(
        id=alert_id(run_id, state.track, state.rule),
        community_id=community_id,
        run_id=run_id,
        anomaly_id=anomaly,
        version=0,
        status="escalated" if escalated else "new",
        triage_status="pending",
        assigned_user_id=staff.supervisor if escalated else staff.user_ids.get(state.guard or ""),
        walk_s=state.walk_s,
        created_ts=state.first_ts,
        updated_ts=state.updated_ts,
    )
    db.add(alert)
    return alert


def _basis(suggestion: Suggestion) -> dict[str, Any]:
    """The next camera's basis as `alert.next_node_basis` stores it (D-20)."""
    basis = asdict(suggestion)
    del basis["node"]
    return basis


def act(
    db: Session, alert: Alert, user: AppUser, action: ActionKind, reason: str, at: datetime
) -> AlertOut:
    """Record a guard's confirm or dismiss at `at`, the run's clock; the caller has locked the
    alert's row and checked it is not handled yet."""
    alert.status = "acked" if action == "confirm" else "dismissed"
    alert.acked_ts = at
    alert.updated_ts = max(alert.updated_ts, at)
    alert.version += 1
    db.add(
        AlertAction(
            id=uuid.uuid4(), alert_id=alert.id, user_id=user.id, action=action, reason=reason, ts=at
        )
    )
    db.flush()
    [out] = load(db, _alerts().where(Alert.id == alert.id))
    return out


def lock(db: Session, community_id: uuid.UUID, id_: uuid.UUID) -> Alert | None:
    """The alert's row, locked until the caller commits; None when it is not the community's."""
    alert = _locked(db, id_)
    return alert if alert is not None and alert.community_id == community_id else None


def _alerts() -> Select[tuple[Alert, Anomaly, str | None]]:
    return (
        select(Alert, Anomaly, Track.anon_id)
        .join(Anomaly, Anomaly.id == Alert.anomaly_id)
        .outerjoin(Track, Track.id == Anomaly.track_id)
    )


def load(db: Session, query: Select[tuple[Alert, Anomaly, str | None]]) -> list[AlertOut]:
    """Alerts with their rule, evidence, people and actions."""
    rows = db.execute(query).all()
    if not rows:
        return []
    actions: dict[uuid.UUID, list[AlertAction]] = {alert.id: [] for alert, _, _ in rows}
    for action in db.scalars(
        select(AlertAction)
        .where(AlertAction.alert_id.in_(actions))
        .order_by(AlertAction.ts, AlertAction.created_at)
    ):
        actions[action.alert_id].append(action)
    user_ids = {alert.assigned_user_id for alert, _, _ in rows if alert.assigned_user_id}
    user_ids |= {action.user_id for done in actions.values() for action in done}
    users = {
        user.id: _user(user) for user in db.scalars(select(AppUser).where(AppUser.id.in_(user_ids)))
    }
    return [
        _out(alert, anomaly, anon_id, actions[alert.id], users) for alert, anomaly, anon_id in rows
    ]


def _user(user: AppUser) -> UserRef:
    return UserRef(id=user.id, code=user.code, name=user.name, role=user.role)  # type: ignore[arg-type]


def _out(
    alert: Alert,
    anomaly: Anomaly,
    anon_id: str | None,
    actions: Iterable[AlertAction],
    users: Mapping[uuid.UUID, UserRef],
) -> AlertOut:
    rule: RuleKey = anomaly.rule_key  # type: ignore[assignment]
    next_node = None
    if alert.next_node_id is not None and alert.next_node_basis is not None:
        basis = NextNodeBasis.model_validate(alert.next_node_basis)
        next_node = NextNodeOut(id=alert.next_node_id, basis=basis)
    assigned = users.get(alert.assigned_user_id) if alert.assigned_user_id else None
    return AlertOut(
        id=alert.id,
        run_id=alert.run_id,
        version=alert.version,
        status=alert.status,  # type: ignore[arg-type]
        rule=rule,
        rule_name=RULE_NAMES[rule],
        detail=anomaly.detail,
        score=anomaly.score,
        # The join finds no track once it has expired (D-56).
        track_id=anomaly.track_id if anon_id is not None else None,
        track_anon_id=anon_id,
        node_id=anomaly.node_id,
        severity=alert.severity,  # type: ignore[arg-type]
        severity_reason=alert.severity_reason,
        triage_status=alert.triage_status,  # type: ignore[arg-type]
        assigned_user=assigned,
        walk_s=alert.walk_s,
        next_node=next_node,
        evidence_event_ids=anomaly.evidence_event_ids,
        created_ts=alert.created_ts,
        updated_ts=alert.updated_ts,
        acked_ts=alert.acked_ts,
        actions=[
            AlertActionOut(
                id=action.id,
                action=action.action,  # type: ignore[arg-type]
                reason=action.reason,
                ts=action.ts,
                user=users[action.user_id],
            )
            for action in actions
        ],
    )


def find_alerts(
    db: Session,
    community_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    status: AlertStatus | None = None,
    limit: int = 500,
) -> list[AlertOut]:
    query = _alerts().where(Alert.community_id == community_id)
    if run_id is not None:
        query = query.where(Alert.run_id == run_id)
    if status is not None:
        query = query.where(Alert.status == status)
    return load(db, query.order_by(Alert.created_ts, Alert.id).limit(limit))


def get_alert(db: Session, community_id: uuid.UUID, id_: uuid.UUID) -> AlertOut | None:
    found = load(db, _alerts().where(Alert.id == id_, Alert.community_id == community_id))
    return found[0] if found else None


def run_alerts(db: Session, run_id: uuid.UUID) -> list[AlertOut]:
    return load(db, _alerts().where(Alert.run_id == run_id).order_by(Alert.created_ts, Alert.id))


def alert_message(kind: MessageType, alert: AlertOut) -> Item:
    """`alert` for a new alert, `alert_update` for a changed one (D-36): each carries it whole."""
    return kind, alert.model_dump(mode="json")
