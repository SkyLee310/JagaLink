from typing import Any

from pydantic import BaseModel


class ErrorOut(BaseModel):
    """The one error body (D-40)."""

    code: str
    message: str
    details: Any = None


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entry documenting the error body for these statuses."""
    return {status: {"model": ErrorOut} for status in statuses}
