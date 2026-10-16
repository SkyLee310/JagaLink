from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, PlainSerializer, StringConstraints, WithJsonSchema

# Human-readable references used by files and scenarios (D-75), e.g. c-gate-02, u-guard-02.
Code = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=40)]


def _iso_millis(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# API timestamps: ISO-8601 in UTC with milliseconds, e.g. 2026-10-17T13:14:00.000Z (D-40).
ApiDatetime = Annotated[
    datetime,
    PlainSerializer(_iso_millis, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]


class ErrorOut(BaseModel):
    """The one error body (D-40)."""

    code: str
    message: str
    details: Any = None


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entry documenting the error body for these statuses."""
    return {status: {"model": ErrorOut} for status in statuses}
