"""From rule matches to alerts (F4, F5): one alert per (track, rule), with its rule-based
severity, the guard it goes to and the camera to check next (D-57–D-60).

Pure and deterministic like the linker (D-32): the caller feeds each sighting with the track the
linker placed it in, and gets back the alerts it opened or changed. The pipeline, the golden
files and the evaluation all run this same code (D-35). What a guard does with an alert (confirm
or dismiss) lives in the database, not here.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from app.engine.graph import Graph
from app.engine.linker import Changes, Linker, Sighting, Track
from app.engine.router import GuardPost, NextCameraWeights, Suggestion, assign, next_camera
from app.engine.rules import RULE_NAMES, Match, RuleKey, RuleSet, Severity, evaluate

ChangeKind = Literal["alert", "alert_update"]


@dataclass
class AlertState:
    track: int
    """The linker's track number."""
    rule: RuleKey
    first_ts: datetime
    """When the rule first matched: the alert's time."""
    last_ts: datetime
    """When the rule last matched."""
    updated_ts: datetime
    """When the alert last changed: a match, or a severity raised by another rule (D-60)."""
    node: str
    """Where the rule last matched: the alert's location."""
    evidence: list[str]
    """Every event the rule relied on, in the order it saw them (D-18)."""
    detail: str
    score: float | None
    severity: Severity
    severity_reason: str
    guard: str | None
    """The assigned guard's code; None means escalated to the supervisor."""
    walk_s: float | None
    next_camera: Suggestion | None


@dataclass(frozen=True)
class AlertChange:
    kind: ChangeKind
    """`alert` for a new alert, `alert_update` for one that changed (D-36, D-59)."""
    alert: AlertState


@dataclass
class Alerter:
    graph: Graph
    rules: RuleSet
    guards: Sequence[GuardPost]
    zone: ZoneInfo
    weights: NextCameraWeights = field(default_factory=NextCameraWeights)
    multi_rule_severity: Severity = "high"
    """D-60: the severity once two or more rules match one track."""
    alerts: dict[tuple[int, RuleKey], AlertState] = field(default_factory=dict)

    def observe(self, track: Track, sighting: Sighting) -> list[AlertChange]:
        """Check the rules after the linker placed `sighting` in `track`."""
        matches = evaluate(track, sighting, self.graph, self.rules, self.zone)
        if not matches:
            return []
        opened: list[AlertState] = []
        changed: dict[RuleKey, AlertState] = {}
        for match in matches:
            state = self.alerts.get((track.number, match.rule))
            if state is None:
                state = self._open(track, match)
                self.alerts[(track.number, match.rule)] = state
                opened.append(state)
            else:
                self._add(state, match, track)
                changed[match.rule] = state
        for state in self._track_alerts(track.number):
            severity, reason = self._severity(state.rule, track.number)
            if (severity, reason) != (state.severity, state.severity_reason):
                state.severity, state.severity_reason = severity, reason
                changed.setdefault(state.rule, state)
        for state in changed.values():
            state.updated_ts = sighting.ts
        new = {state.rule for state in opened}
        updates = [state for rule, state in changed.items() if rule not in new]
        return [AlertChange("alert", _snapshot(state)) for state in opened] + [
            AlertChange("alert_update", _snapshot(state)) for state in updates
        ]

    def forget(self, track: int) -> None:
        """The track expired (D-56): its alerts stay in the database, the state here goes."""
        for key in [key for key in self.alerts if key[0] == track]:
            del self.alerts[key]

    def _open(self, track: Track, match: Match) -> AlertState:
        assignment = assign(self.graph, self.guards, match.node)
        return AlertState(
            track=track.number,
            rule=match.rule,
            first_ts=match.ts,
            last_ts=match.ts,
            updated_ts=match.ts,
            node=match.node,
            evidence=list(dict.fromkeys(match.evidence)),
            detail=match.detail,
            score=match.score,
            severity=self.rules.severity(match.rule),
            severity_reason="",
            guard=assignment.guard,
            walk_s=assignment.walk_s,
            next_camera=next_camera(self.graph, track.nodes(), self.weights),
        )

    def _add(self, state: AlertState, match: Match, track: Track) -> None:
        """A repeat match adds evidence to the open alert, not a new one (D-59)."""
        state.last_ts, state.node = match.ts, match.node
        state.evidence = list(dict.fromkeys([*state.evidence, *match.evidence]))
        state.detail, state.score = match.detail, match.score
        state.next_camera = next_camera(self.graph, track.nodes(), self.weights)

    def _track_alerts(self, track: int) -> list[AlertState]:
        return [state for (number, _), state in self.alerts.items() if number == track]

    def _severity(self, rule: RuleKey, track: int) -> tuple[Severity, str]:
        """D-60: each rule's own severity, raised when two or more rules match one track."""
        rules = sorted({state.rule for state in self._track_alerts(track)})
        if len(rules) >= 2:
            names = ", ".join(RULE_NAMES[key].lower() for key in rules)
            reason = f"Rule-based: {len(rules)} rules matched this path ({names})."
            return self.multi_rule_severity, reason
        severity = self.rules.severity(rule)
        return severity, f"Rule-based: {RULE_NAMES[rule].lower()} is rated {severity}."


def _snapshot(state: AlertState) -> AlertState:
    return replace(state, evidence=list(state.evidence))


def link_and_check(
    linker: Linker, alerter: Alerter, sighting: Sighting
) -> tuple[Changes, list[AlertChange]]:
    """One event through F3 and F4, as the pipeline, the golden files and the evaluation all run
    it (D-35): link it, forget the alerts of tracks that expired, check the rules on its track."""
    changes = linker.feed(sighting)
    for number in changes.expired:
        alerter.forget(number)
    assert changes.placed is not None  # feed always places its sighting
    return changes, alerter.observe(changes.placed, sighting)
