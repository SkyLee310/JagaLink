"""Live runs (F2, D-77): one playing scenario per community, its state in the database.

The API's sync routes call in from worker threads; each player is a task on the app's event loop.
A played batch goes through the same ingest and pipeline as `POST /events` (D-30), in a worker
thread, and then out to the run's stream. While a player runs, a route touches the database only
before it starts or after it has stopped the player: tests share one session between the two.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.hub import Hub, Item
from app.core.pipeline import Pipelines
from app.db import alert_store, event_store, track_store
from app.db.layout_store import export_layout
from app.db.models import Anomaly, AppUser, Community, Event, Node, Scenario, ScenarioRun, Track
from app.db.session import get_engine
from app.engine.clock import SimClock
from app.schemas.events import EventIn
from app.schemas.scenarios import RunOut, ScenarioOut
from app.sim.player import Player, Timer, WallTimer
from app.sim.scenario import (
    SCENARIO_DIR,
    NightClock,
    ScenarioFile,
    check_scenario,
    graph_from_layout,
    load_scenario,
)
from app.sim.script import ScriptEvent, build_script

logger = logging.getLogger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]


def default_scope() -> Session:
    return Session(get_engine())


@dataclass(frozen=True)
class Prepared:
    """What a run plays: its scenario's live window on the community's current layout."""

    file: ScenarioFile
    events: list[ScriptEvent]
    node_ids: dict[str, uuid.UUID]
    window_start: datetime
    window_end: datetime


@dataclass
class LiveRun:
    community_id: uuid.UUID
    player: Player
    task: asyncio.Task[None]


@dataclass(frozen=True)
class Snapshot:
    emitted: int
    clock: datetime
    done: bool


def scenario_file(scenario: Scenario) -> ScenarioFile:
    return load_scenario(SCENARIO_DIR / scenario.script_path)


def describe_scenario(scenario: Scenario, community: Community) -> ScenarioOut:
    file = scenario_file(scenario)
    clock = NightClock(file.night, community.timezone)
    return ScenarioOut(
        id=scenario.id,
        code=scenario.code,
        name=scenario.name,
        description=scenario.description,
        duration_s=scenario.duration_s,
        default_speed=file.default_speed,
        window_start=clock.at(file.live_window.start),
        window_end=clock.at(file.live_window.end),
    )


def list_scenarios(db: Session, community: Community) -> list[ScenarioOut]:
    rows = db.scalars(
        select(Scenario).where(Scenario.community_id == community.id).order_by(Scenario.code)
    )
    return [describe_scenario(row, community) for row in rows]


def prepare(db: Session, community: Community, scenario: Scenario) -> Prepared:
    """Build the run's events on the current layout; refuse a scenario that no longer fits it."""
    file = scenario_file(scenario)
    layout = export_layout(db, community)
    graph = graph_from_layout(layout)
    users = list(db.scalars(select(AppUser.code).where(AppUser.community_id == community.id)))
    problems = check_scenario(file, graph, users)
    if problems:
        message = "The scenario no longer fits the community's layout or staff"
        raise ApiError(409, "scenario_does_not_fit", message, problems)
    script = build_script(file, graph, community.timezone)
    return Prepared(
        file=file,
        events=script.live_events(),
        node_ids=node_ids(db, community),
        window_start=script.window_start,
        window_end=script.window_end,
    )


def node_ids(db: Session, community: Community) -> dict[str, uuid.UUID]:
    query = select(Node.code, Node.id).where(Node.community_id == community.id)
    return {code: node_id for code, node_id in db.execute(query)}


def apply_roster(db: Session, community: Community, file: ScenarioFile) -> None:
    """Guards stand where the scenario puts them for the whole run (D-58)."""
    roster = {entry.user: entry for entry in file.roster}
    nodes = node_ids(db, community)
    for user in db.scalars(select(AppUser).where(AppUser.community_id == community.id)):
        entry = roster.get(user.code)
        if entry is not None:
            user.on_duty = entry.on_duty
            user.current_node_id = nodes[entry.node] if entry.node else None
        elif user.role == "guard":
            user.on_duty, user.current_node_id = False, None


def clear_run(db: Session, run_id: uuid.UUID) -> None:
    """Delete what a run produced, so it can play again from the start."""
    db.execute(delete(Anomaly).where(Anomaly.run_id == run_id))  # with their alerts and actions
    db.execute(delete(Track).where(Track.run_id == run_id))
    db.execute(delete(Event).where(Event.run_id == run_id))


def run_backlog(db: Session, run_id: uuid.UUID) -> list[Item]:
    """The stream messages that bring a new subscriber up to date with the run (D-36). Its
    alerts come as `alert_update`: they are not new to the run."""
    events = db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.seq))
    items = [event_store.event_message(event) for event in events]
    items += [track_store.track_message(track) for track in track_store.run_tracks(db, run_id)]
    return items + [
        alert_store.alert_message("alert_update", alert)
        for alert in alert_store.run_alerts(db, run_id)
    ]


class RunManager:
    def __init__(
        self,
        hub: Hub | None = None,
        timer: Timer | None = None,
        session_scope: SessionScope = default_scope,
        pipelines: Pipelines | None = None,
    ) -> None:
        self.hub = hub or Hub()
        self.timer: Timer = timer or WallTimer()
        self.session_scope = session_scope
        self.pipelines = pipelines or Pipelines()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.live: dict[uuid.UUID, LiveRun] = {}
        self.prepared: dict[uuid.UUID, Prepared] = {}

    # Event loop plumbing ------------------------------------------------------------------

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.hub.bind(loop)

    def _on_loop[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        """Run a coroutine on the app's loop from a worker thread, and wait for it."""
        if self.loop is None:
            coroutine.close()
            raise RuntimeError("the run manager is not bound to an event loop")
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()

    async def shutdown(self) -> None:
        for run_id in list(self.live):
            await self._retire(run_id)

    async def wait(self, run_id: uuid.UUID) -> None:
        """Until the run's player stops: at the end of the window, or when told to."""
        live = self.live.get(run_id)
        if live is not None:
            await asyncio.shield(live.task)

    # Routes call these from worker threads -----------------------------------------------

    def current(self, db: Session, community: Community) -> RunOut | None:
        """The community's live run that has not been stopped, if any."""
        run = db.scalars(
            select(ScenarioRun)
            .where(
                ScenarioRun.community_id == community.id,
                ScenarioRun.mode == "live",
                ScenarioRun.state != "stopped",
            )
            .order_by(ScenarioRun.created_at.desc())
        ).first()
        if run is None:
            return None
        if run.state == "playing" and run.id not in self.live:
            # The process restarted under a playing run: it waits, paused, to be resumed.
            run.state = "paused"
            db.commit()
        return self.describe(db, community, run)

    def start(
        self, db: Session, community: Community, scenario: Scenario, speed: float | None
    ) -> RunOut:
        """Stop the community's live run, put the guards in place, and play the scenario."""
        prepared = prepare(db, community, scenario)
        previous = db.scalars(
            select(ScenarioRun).where(
                ScenarioRun.community_id == community.id,
                ScenarioRun.mode == "live",
                ScenarioRun.state != "stopped",
            )
        ).all()
        for old in previous:
            self._on_loop(self._retire(old.id))
            old.state = "stopped"
        db.flush()
        apply_roster(db, community, prepared.file)
        run = ScenarioRun(
            id=uuid.uuid4(),
            community_id=community.id,
            scenario_id=scenario.id,
            mode="live",
            speed=speed or prepared.file.default_speed,
            state="playing",
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        self.prepared[run.id] = prepared
        return self._launch(db, community, run, prepared)

    def pause(self, db: Session, community: Community, run: ScenarioRun) -> RunOut:
        if run.state != "playing":
            raise ApiError(409, "run_not_playing", f"The run is {run.state}, not playing")
        outcome = self._on_loop(self._pause(run.id))
        if outcome == "done":
            raise ApiError(409, "run_finished", "The run has just finished")
        run.state = "paused"
        db.commit()
        return self.describe(db, community, run)

    def resume(
        self, db: Session, community: Community, run: ScenarioRun, speed: float | None
    ) -> RunOut:
        """Play a ready or paused run; on a playing run, only change its speed."""
        if run.state not in ("ready", "paused", "playing"):
            raise ApiError(
                409, "run_closed", f"The run is {run.state}; reset it or start a new one"
            )
        if speed is not None:
            run.speed = speed
        run.state = "playing"
        db.commit()
        if self._on_loop(self._resume(run.id, speed)) == "resumed":
            return self.describe(db, community, run)
        prepared = self._prepared(db, community, run)
        return self._launch(db, community, run, prepared)

    def reset(self, db: Session, community: Community, run: ScenarioRun) -> RunOut:
        """Stop the player and clear the run's events, ready to play again from the start."""
        if run.state == "stopped":
            raise ApiError(409, "run_closed", "The run was replaced by a newer one")
        self._on_loop(self._retire(run.id))
        clear_run(db, run.id)
        run.state = "ready"
        db.commit()
        return self.describe(db, community, run)

    def describe(self, db: Session, community: Community, run: ScenarioRun) -> RunOut:
        scenario = db.get_one(Scenario, run.scenario_id)
        prepared = self._prepared(db, community, run)
        snapshot = self._on_loop(self._snapshot(run.id)) if self.loop else None
        if snapshot is not None:
            emitted, clock = snapshot.emitted, snapshot.clock
        else:
            emitted = event_store.event_count(db, run.id)
            clock = self._resting_clock(db, community, run)
        return RunOut(
            id=run.id,
            scenario_id=scenario.id,
            scenario_code=scenario.code,
            scenario_name=scenario.name,
            mode=run.mode,
            speed=run.speed,
            state=run.state,
            started_at=run.started_at,
            window_start=prepared.window_start,
            window_end=prepared.window_end,
            clock=clock,
            events_emitted=emitted,
            events_total=len(prepared.events),
        )

    def clock(self, db: Session, community: Community, run: ScenarioRun) -> datetime:
        """Where the run's clock stands, in event time (D-31): its player's position, or where
        the run rests."""
        snapshot = self._on_loop(self._snapshot(run.id)) if self.loop else None
        return snapshot.clock if snapshot is not None else self._resting_clock(db, community, run)

    def backlog(self, run_id: uuid.UUID, community_id: uuid.UUID) -> list[Item]:
        """A run's stream backlog, read with a session of its own (a stream outlives requests)."""
        with self.session_scope() as db:
            run = db.get(ScenarioRun, run_id)
            if run is None or run.community_id != community_id:
                raise ApiError(404, "run_not_found", "No run in your community has that ID")
            return run_backlog(db, run_id)

    # Internals -------------------------------------------------------------------------------

    def _prepared(self, db: Session, community: Community, run: ScenarioRun) -> Prepared:
        prepared = self.prepared.get(run.id)
        if prepared is None:
            prepared = prepare(db, community, db.get_one(Scenario, run.scenario_id))
            self.prepared[run.id] = prepared
        return prepared

    def _resting_clock(self, db: Session, community: Community, run: ScenarioRun) -> datetime:
        """Where a run without a player stands: its start, its end, or its latest event."""
        if run.state == "ready":
            return self._prepared(db, community, run).window_start
        if run.state == "finished":
            return self._prepared(db, community, run).window_end
        last = db.scalar(
            select(Event.ts).where(Event.run_id == run.id).order_by(Event.seq.desc()).limit(1)
        )
        return last or self._prepared(db, community, run).window_start

    def _launch(
        self, db: Session, community: Community, run: ScenarioRun, prepared: Prepared
    ) -> RunOut:
        """Start a player from the run's latest stored event; describe the run first."""
        emitted = event_store.event_count(db, run.id)
        position = self._resting_clock(db, community, run)
        backlog = run_backlog(db, run.id) if self.hub.channel(run.id) is None else []
        out = self.describe(db, community, run)
        clock = SimClock(position, anchor=0.0, speed=run.speed)
        self._on_loop(self._spawn(run.id, community.id, prepared, clock, emitted, backlog))
        return out

    async def _spawn(
        self,
        run_id: uuid.UUID,
        community_id: uuid.UUID,
        prepared: Prepared,
        clock: SimClock,
        emitted: int,
        backlog: list[Item],
    ) -> None:
        self.hub.open(run_id, community_id, backlog)
        emit = partial(self._emit, run_id, prepared)
        player = Player(prepared.events, clock, prepared.window_end, self.timer, emit, emitted)
        player.resume()
        task = asyncio.get_running_loop().create_task(self._play(run_id, player))
        self.live[run_id] = LiveRun(community_id, player, task)

    async def _play(self, run_id: uuid.UUID, player: Player) -> None:
        try:
            finished = await player.run()
        except Exception:
            logger.exception("Run %s paused: a batch of its events could not be stored", run_id)
            player.clock.pause(self.timer.now())
            await asyncio.to_thread(self._settle, run_id, "paused")
            return
        if finished:
            items = await asyncio.to_thread(self._settle, run_id, "finished", player.end)
            self.hub.publish(run_id, items)

    def _settle(
        self,
        run_id: uuid.UUID,
        state: Literal["paused", "finished"],
        end: datetime | None = None,
    ) -> list[Item]:
        """Record where the player stopped; at the end of the window, close the run's tracks."""
        items: list[Item] = []
        with self.session_scope() as db:
            run = db.get(ScenarioRun, run_id)
            if run is not None and run.state in ("playing", "paused"):
                run.state = state
                if state == "finished" and end is not None:
                    items = self.pipelines.finish(db, run, end)
                db.commit()
        return items

    async def _emit(self, run_id: uuid.UUID, prepared: Prepared, batch: list[ScriptEvent]) -> None:
        # The player posts the event contract only: never the object behind it (D-70).
        events = [
            EventIn(
                run_id=run_id,
                ts=event.ts,
                node_id=prepared.node_ids[event.node],
                type=event.type,
                object_class=event.object_class,
                local_track_id=event.local_track_id,
                source="sim",
            )
            for event in batch
        ]
        items = await asyncio.to_thread(self._store, run_id, events)
        self.hub.publish(run_id, items)

    def _store(self, run_id: uuid.UUID, events: list[EventIn]) -> list[Item]:
        with self.session_scope() as db:
            run = db.get_one(ScenarioRun, run_id)
            return self.ingest(db, run, events)

    def ingest(self, db: Session, run: ScenarioRun, events: list[EventIn]) -> list[Item]:
        """Store a batch, run it through the pipeline and commit; the stream messages for it."""
        stored = event_store.ingest(db, run, events)
        try:
            items = [event_store.event_message(event) for event in stored]
            items += self.pipelines.process(db, run, stored)
            db.commit()
        except Exception:
            self.pipelines.forget(run.id)
            raise
        return items

    async def _retire(self, run_id: uuid.UUID) -> None:
        """Stop the run's player, waiting out any batch in flight, and end its streams."""
        live = self.live.pop(run_id, None)
        if live is not None:
            live.player.stop()
            await live.task
        self.prepared.pop(run_id, None)
        self.pipelines.forget(run_id)
        self.hub.close(run_id)

    async def _pause(self, run_id: uuid.UUID) -> Literal["paused", "done", "absent"]:
        live = self.live.get(run_id)
        if live is None or live.task.done():
            return "absent"
        if live.player.done:
            return "done"
        live.player.pause()
        return "paused"

    async def _resume(self, run_id: uuid.UUID, speed: float | None) -> Literal["resumed", "absent"]:
        live = self.live.get(run_id)
        if live is None or live.task.done():
            self.live.pop(run_id, None)
            return "absent"
        live.player.resume(speed)
        return "resumed"

    async def _snapshot(self, run_id: uuid.UUID) -> Snapshot | None:
        live = self.live.get(run_id)
        if live is None:
            return None
        return Snapshot(live.player.index, live.player.position(), live.player.done)
