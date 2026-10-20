"""What every stored batch of events goes through (D-30): the path linker (F3) turns it into
tracks, which are written beside the events and pushed on the run's stream.

Each run's linker lives in memory (D-77). When it is missing, after a restart or a failed batch,
it is rebuilt by replaying the run's stored events, which gives back the same tracks: linking is
deterministic (D-27). Batches of every run pass one at a time.
"""

import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hub import Item
from app.db import track_store
from app.db.layout_store import export_layout
from app.db.models import Community, Event, Node, ScenarioRun
from app.engine.linker import DEFAULT_TTL_S, Changes, Linker, Sighting
from app.sim.scenario import graph_from_layout


@dataclass
class RunLinks:
    """One run's linker, and the node lookups between event UUIDs and graph codes (D-75)."""

    linker: Linker
    codes: dict[uuid.UUID, str]
    node_ids: dict[str, uuid.UUID]


class Pipelines:
    def __init__(self, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.ttl_s = ttl_s
        """Seconds a track lives after its last sighting (D-56); the demo may shorten it."""
        self.runs: dict[uuid.UUID, RunLinks] = {}
        self.lock = threading.Lock()

    def process(self, db: Session, run: ScenarioRun, stored: Sequence[Event]) -> list[Item]:
        """Link a batch the caller has just stored; write the tracks it changed and return
        their stream messages. The caller commits, and calls `forget` if the commit fails."""
        if not stored:
            return []
        with self.lock:
            try:
                links = self.runs.get(run.id) or self._rebuild(db, run, before=stored[0].seq)
                self.runs[run.id] = links
                changes = Changes()
                for event in stored:
                    changes.merge(links.linker.feed(self._sighting(db, links, event)))
                return self._write(db, run, links, changes, now=stored[-1].ts)
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
        """Drop a run's linker; the next batch rebuilds it from the database."""
        with self.lock:
            self.runs.pop(run_id, None)

    def _rebuild(self, db: Session, run: ScenarioRun, before: int | None) -> RunLinks:
        graph = graph_from_layout(export_layout(db, db.get_one(Community, run.community_id)))
        links = RunLinks(Linker(graph, self.ttl_s), {}, {})
        self._load_nodes(db, run.community_id, links)
        query = select(Event).where(Event.run_id == run.id).order_by(Event.seq)
        if before is not None:
            query = query.where(Event.seq < before)
        for event in db.scalars(query):
            links.linker.feed(self._sighting(db, links, event))
        return links

    def _load_nodes(self, db: Session, community_id: uuid.UUID, links: RunLinks) -> None:
        query = select(Node.code, Node.id).where(Node.community_id == community_id)
        links.node_ids = {code: node_id for code, node_id in db.execute(query)}
        links.codes = {node_id: code for code, node_id in links.node_ids.items()}

    def _sighting(self, db: Session, links: RunLinks, event: Event) -> Sighting:
        if event.node_id not in links.codes:
            # The layout gained a node since the linker was built: read it again.
            community = db.get_one(Community, event.community_id)
            links.linker.graph = graph_from_layout(export_layout(db, community))
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
        self, db: Session, run: ScenarioRun, links: RunLinks, changes: Changes, now: datetime
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
        track_store.remove(db, [track.id for track in expired])
        # The purge job (D-11): anything in the community past its expiry by now, in event time.
        track_store.purge_expired(db, run.community_id, now)
        return [track_store.track_message(out) for _, out in updated] + [
            track_store.track_message(out) for out in expired
        ]
