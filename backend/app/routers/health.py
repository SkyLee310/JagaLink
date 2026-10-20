from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
def health(db: Annotated[Session, Depends(get_db)]) -> HealthOut | JSONResponse:
    """Health probe: 200 when the database answers, 503 when it does not."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        down = HealthOut(status="degraded", db="down")
        return JSONResponse(down.model_dump(), status_code=503)
    return HealthOut(status="ok", db="ok")
