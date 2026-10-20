"""What every stored batch of events goes through (D-30): the path linker (F3) turns it into
tracks, the rules (F4) and the router (F5) turn the tracks into alerts, and both are written
beside the events and pushed on the run's stream.

Each run's linker and alerter live in memory (D-77). When they are missing, after a restart or a
failed batch, they are rebuilt by replaying the run's stored events, which gives back the same
tracks and alerts: both are deterministic (D-27). Every batch reads the community's rules and
guards afresh, so a threshold changed through the API applies from the next batch (F4). Batches
of every run pass one at a time.
"""

import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hub import Item
from app.db import alert_store, rule_store, track_store
from app.db.layout_store import export_layout
from app.db.models import AppUser, Community, Event, Node, ScenarioRun
from app.engine.alerting import AlertChange, Alerter, link_and_check
from app.engine.linker import DEFAULT_TTL_S, Changes, Linker, Sighting
from app.engine.router import GuardPost, NextCameraWeights
from app.engine.rules import RuleSet, Severity
from app.sim.scenario import graph_from_layout


@dataclass
class RunLinks:
    """One run's linker and alerter, and the node lookups between event UUIDs and graph codes
    (D-75)."""

    linker: Linker
    alerter: Alerter
    codes: dict[uuid.UUID, str]
    node_ids: dict[str, uuid.UUID]


class Pipelines:
    def __init__(
        self,
        ttl_s: float = DEFAULT_TTL_S,
        weights: NextCameraWeights | None = None,
        multi_rule_severity: Severity = "high",
    ) -> None:
        self.ttl_s = ttl_s
        """Seconds a track lives after its last sighting (D-56); the demo may shorten it."""
        self.weights = weights or NextCameraWeights()
        self.multi_rule_severity = multi_rule_severity
        self.runs: dict[uuid.UUID, RunLinks] = {}
        self.lock = threading.Lock()

    def process(self, db: Session, run: ScenarioRun, stored: Sequence[Event]) -> list[Item]:
        """Link a batch the caller has just stored and check the rules after each event; write
        the tracks and alerts it changed and return their stream messages. The caller commits,
        and calls `forget` if the commit fails."""
        if not stored:
            return []
        with self.lock:
            try:
                links = self.runs.get(run.id) or self._rebuild(db, run, before=stored[0].seq)
                self.runs[run.id] = links
                staff = self._staff(db, run.community_id, links)
                changes = Changes()
                alerts: list[AlertChange] = []
                for event in stored:
                    step, found = link_and_check(
                        links.linker, links.alerter, self._sighting(db, links, event)
                    )
                    changes.merge(step)
                    alerts += found
                return self._write(db, run, links, changes, stored[-1].ts, alerts, staff)
            except Exception:
                self.runs.pop(run.id, None)
                raise

    def finish(self, db: Session, run: ScenarioRun, end: datetime) -> list[Item]:
        """The run has played to `end`: tracks due to expire by then go, every other closes."""
        with self.lock:
            links = self.runs.pop(run.id, None) or self._rebuild(db, run, before=None)
            changes = links.linker.advance(end).merge(links.linker.finish())
            return self._write(db, run, links, changes, now=end)

    def forget(self, run_id: uuid.UUID) -> None:
        """Drop a run's linker and alerter; the next batch rebuilds them from the database."""
        with self.lock:
            self.runs.pop(run_id, None)

    def _rebuild(self, db: Session, run: ScenarioRun, before: int | None) -> RunLinks:
        community = db.get_one(Community, run.community_id)
        graph = graph_from_layout(export_layout(db, community))
        zone = ZoneInfo(community.timezone)
        alerter = Alerter(graph, RuleSet(), [], zone, self.weights, self.multi_rule_severity)
        links = RunLinks(Linker(graph, self.ttl_s), alerter, {}, {})
        self._load_nodes(db, run.community_id, links)
        self._staff(db, run.community_id, links)
        query = select(Event).where(Event.run_id == run.id).order_by(Event.seq)
        if before is not None:
            query = query.where(Event.seq < before)
        for event in db.scalars(query):
            # The replay's alerts are stored already.
            link_and_check(links.linker, links.alerter, self._sighting(db, links, event))
        return links

    def _load_nodes(self, db: Session, community_id: uuid.UUID, links: RunLinks) -> None:
        query = select(Node.code, Node.id).where(Node.community_id == community_id)
        links.node_ids = {code: node_id for code, node_id in db.execute(query)}
        links.codes = {node_id: code for code, node_id in links.node_ids.items()}

    def _staff(self, db: Session, community_id: uuid.UUID, links: RunLinks) -> alert_store.Staff:
        """Give the alerter the community's rules and guard posts as they stand now (F4, D-58);
        who its alerts go to."""
        links.alerter.rules = rule_store.load_rules(db, community_id)
        users = list(
            db.scalars(
                select(AppUser).where(AppUser.community_id == community_id).order_by(AppUser.code)
            )
        )
        links.alerter.guards = [
            GuardPost(user.code, links.codes.get(user.current_node_id), user.on_duty)  # type: ignore[arg-type]
            for user in users
            if user.role == "guard"
        ]
        # An escalated alert goes to the first supervisor on duty, else the first supervisor.
        supervisors = sorted(
            (user for user in users if user.role == "supervisor"), key=lambda user: not user.on_duty
        )
        supervisor = supervisors[0].id if supervisors else None
        return alert_store.Staff({user.code: user.id for user in users}, supervisor)

    def _sighting(self, db: Session, links: RunLinks, event: Event) -> Sighting:
        if event.node_id not in links.codes:
            # The layout gained a node since the linker was built: read it again.
            community = db.get_one(Community, event.community_id)
            links.linker.graph = graph_from_layout(export_layout(db, community))
            links.alerter.graph = links.linker.graph
            self._load_nodes(db, community.id, links)
        return Sighting(
            id=str(event.id),
            ts=event.ts,
            node=links.codes[event.node_id],
            type=event.type,
            object_class=event.object_class,
            local_track_id=event.local_track_id,
        )

    def _write(
        self,
        db: Session,
        run: ScenarioRun,
        links: RunLinks,
        changes: Changes,
        now: datetime,
        alerts: Sequence[AlertChange] = (),
        staff: alert_store.Staff | None = None,
    ) -> list[Item]:
        updated = [
            (number, track_store.track_out(run.id, track, links.node_ids))
            for number, track in sorted(changes.updated.items())
        ]
        expired = [
            track_store.track_out(run.id, track, links.node_ids)
            for _, track in sorted(changes.expired.items())
        ]
        track_store.save(db, run.community_id, updated)
        # Alerts go after the tracks they point to, and before any track is deleted.
        alert_items: list[Item] = []
        if alerts and staff is not None:
            alert_items = alert_store.save(
                db, run.community_id, run.id, alerts, links.node_ids, staff
            )
        track_store.remove(db, [track.id for track in expired])
        # The purge job (D-11): anything in the community past its expiry by now, in event time.
        track_store.purge_expired(db, run.community_id, now)
        track_items = [track_store.track_message(out) for _, out in updated] + [
            track_store.track_message(out) for out in expired
        ]
        return track_items + alert_items
