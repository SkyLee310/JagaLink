from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.core.errors import ApiError
from app.db.models import AppUser, Community, Scenario, ScenarioRun
from app.db.session import get_db
from app.schemas.common import error_responses
from app.schemas.scenarios import RunCreate, RunOut, RunResume, ScenarioOut
from app.sim.runs import RunManager, list_scenarios

router = APIRouter(tags=["scenarios"])

Db = Annotated[Session, Depends(get_db)]
User = Annotated[AppUser, Depends(current_user)]
# The scenario player is a supervisor screen (D-66); guards only follow the current run.
Supervisor = Annotated[AppUser, Depends(require_role("supervisor"))]


def get_runs(request: Request) -> RunManager:
    return request.app.state.runs


Runs = Annotated[RunManager, Depends(get_runs)]


def own_run(db: Session, user: AppUser, run_id: UUID) -> ScenarioRun:
    run = db.get(ScenarioRun, run_id)
    if run is None or run.community_id != user.community_id:
        raise ApiError(404, "run_not_found", "No run in your community has that ID")
    return run


def _community(db: Session, user: AppUser) -> Community:
    return db.get_one(Community, user.community_id)


@router.get("/scenarios", responses=error_responses(401, 403))
def get_scenarios(user: Supervisor, db: Db) -> list[ScenarioOut]:
    """Scripted scenarios with their live window; never their ground truth (D-70)."""
    return list_scenarios(db, _community(db, user))


@router.post("/scenario-runs", status_code=201, responses=error_responses(401, 403, 404, 409, 422))
def start_run(body: RunCreate, user: Supervisor, db: Db, runs: Runs) -> RunOut:
    """Play a scenario. The community's previous live run stops (D-77), and the guards take
    the places the scenario's roster gives them (D-58). 409 when the scenario no longer fits
    the layout or staff, with each problem in `details`.
    """
    scenario = db.get(Scenario, body.scenario_id)
    if scenario is None or scenario.community_id != user.community_id:
        raise ApiError(404, "scenario_not_found", "No scenario in your community has that ID")
    return runs.start(db, _community(db, user), scenario, body.speed)


@router.get("/scenario-runs/current", responses=error_responses(401))
def current_run(user: User, db: Db, runs: Runs) -> RunOut | None:
    """The community's live run, or null when none has been started (or it was replaced)."""
    return runs.current(db, _community(db, user))


@router.get("/scenario-runs/{run_id}", responses=error_responses(401, 404, 422))
def get_run(run_id: UUID, user: User, db: Db, runs: Runs) -> RunOut:
    return runs.describe(db, _community(db, user), own_run(db, user, run_id))


@router.post("/scenario-runs/{run_id}/pause", responses=error_responses(401, 403, 404, 409, 422))
def pause_run(run_id: UUID, user: Supervisor, db: Db, runs: Runs) -> RunOut:
    return runs.pause(db, _community(db, user), own_run(db, user, run_id))


@router.post("/scenario-runs/{run_id}/resume", responses=error_responses(401, 403, 404, 409, 422))
def resume_run(
    run_id: UUID,
    user: Supervisor,
    db: Db,
    runs: Runs,
    body: Annotated[RunResume | None, Body()] = None,
) -> RunOut:
    """Play a ready or paused run; on a playing run, only change its speed."""
    speed = body.speed if body else None
    return runs.resume(db, _community(db, user), own_run(db, user, run_id), speed)


@router.post("/scenario-runs/{run_id}/reset", responses=error_responses(401, 403, 404, 409, 422))
def reset_run(run_id: UUID, user: Supervisor, db: Db, runs: Runs) -> RunOut:
    """Stop playback and clear the run's events and derived rows; it can play again."""
    return runs.reset(db, _community(db, user), own_run(db, user, run_id))
