"""Rule thresholds (F4) as the API reads and writes them. `rule_config.params` stores the same
fields, so a supervisor changes a threshold without a code change (D-18)."""

from datetime import time
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine.rules import Severity, ZoneKind


class AfterHoursParams(BaseModel):
    """An appearance in a zone of one of `zone_kinds` from `start` to `end` in the community's
    time zone; the period may span midnight (D-54)."""

    model_config = ConfigDict(extra="forbid")

    start: time
    end: time
    zone_kinds: list[ZoneKind] = Field(min_length=1)
    severity: Severity


class LoiterParams(BaseModel):
    """At least `threshold_s` in one zone within the last `window_s` (D-52)."""

    model_config = ConfigDict(extra="forbid")

    threshold_s: float = Field(gt=0)
    window_s: float = Field(gt=0)
    severity: Severity

    @model_validator(mode="after")
    def threshold_fits_the_window(self) -> Self:
        if self.threshold_s > self.window_s:
            raise ValueError("threshold_s cannot be longer than window_s")
        return self


class OffRouteParams(BaseModel):
    """A step between two nodes that no normal route takes (D-53)."""

    model_config = ConfigDict(extra="forbid")

    severity: Severity


class AfterHoursRule(BaseModel):
    key: Literal["after_hours"]
    name: str
    enabled: bool
    params: AfterHoursParams


class LoiterRule(BaseModel):
    key: Literal["loiter"]
    name: str
    enabled: bool
    params: LoiterParams


class OffRouteRule(BaseModel):
    key: Literal["off_route"]
    name: str
    enabled: bool
    params: OffRouteParams


RuleOut = Annotated[AfterHoursRule | LoiterRule | OffRouteRule, Field(discriminator="key")]
"""One rule with its thresholds; `params` follows the rule's `key`. Its `severity` is the
rule-based severity of its alerts (D-60)."""


class RuleUpdate(BaseModel):
    """What to change; leave out what stays. Each field in `params` replaces the stored one."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    params: dict[str, Any] | None = None
