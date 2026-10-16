from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

# Human-readable references used by files and scenarios (D-75), e.g. c-gate-02, u-guard-02.
Code = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=40)]


class ErrorOut(BaseModel):
    """The one error body (D-40)."""

    code: str
    message: str
    details: Any = None


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entry documenting the error body for these statuses."""
    return {status: {"model": ErrorOut} for status in statuses}
