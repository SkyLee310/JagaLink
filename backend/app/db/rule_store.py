"""Rule thresholds (F4): `rule_config` rows to the engine's `RuleSet` and back. The caller commits.

The engine's defaults (D-52–D-54, D-60) seed every community; a rule with no row keeps them.
"""

import uuid
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import RuleConfig
from app.engine.rules import RULE_KEYS, RULE_NAMES, AfterHours, Loiter, OffRoute, RuleKey, RuleSet
from app.schemas.rules import AfterHoursParams, LoiterParams, OffRouteParams, RuleOut, RuleUpdate

Rule = AfterHours | Loiter | OffRoute
Params = AfterHoursParams | LoiterParams | OffRouteParams

PARAMS: dict[RuleKey, type[Params]] = {
    "after_hours": AfterHoursParams,
    "loiter": LoiterParams,
    "off_route": OffRouteParams,
}
RULE_OUT: TypeAdapter[RuleOut] = TypeAdapter(RuleOut)


def rule_id(community_id: uuid.UUID, key: RuleKey) -> uuid.UUID:
    return uuid.uuid5(community_id, f"rule-{key}")


def params_of(rule: Rule) -> dict[str, Any]:
    """A rule's thresholds as `rule_config.params` stores them."""
    params: Params
    match rule:
        case AfterHours():
            kinds = sorted(rule.zone_kinds)
            params = AfterHoursParams(
                start=rule.start, end=rule.end, zone_kinds=kinds, severity=rule.severity
            )
        case Loiter():
            params = LoiterParams(
                threshold_s=rule.threshold_s, window_s=rule.window_s, severity=rule.severity
            )
        case OffRoute():
            params = OffRouteParams(severity=rule.severity)
    return params.model_dump(mode="json")


def rule_of(key: RuleKey, enabled: bool, params: dict[str, Any]) -> Rule:
    """Stored thresholds as the engine reads them; ValidationError when they are not valid."""
    checked = PARAMS[key].model_validate(params)
    match checked:
        case AfterHoursParams():
            kinds = frozenset(checked.zone_kinds)
            return AfterHours(enabled, checked.start, checked.end, kinds, checked.severity)
        case LoiterParams():
            return Loiter(enabled, checked.threshold_s, checked.window_s, checked.severity)
        case OffRouteParams():
            return OffRoute(enabled, checked.severity)


def seed_rules(db: Session, community_id: uuid.UUID) -> None:
    """Give the community each rule it lacks, at the engine's defaults; edited rules stay."""
    present = set(
        db.scalars(select(RuleConfig.rule_key).where(RuleConfig.community_id == community_id))
    )
    defaults = RuleSet()
    for key in RULE_KEYS:
        if key not in present:
            rule: Rule = getattr(defaults, key)
            db.add(
                RuleConfig(
                    id=rule_id(community_id, key),
                    community_id=community_id,
                    rule_key=key,
                    params=params_of(rule),
                    enabled=rule.enabled,
                )
            )
    db.flush()


def load_rules(db: Session, community_id: uuid.UUID) -> RuleSet:
    """The community's rules as the engine runs them."""
    rows = db.scalars(select(RuleConfig).where(RuleConfig.community_id == community_id))
    stored = {row.rule_key: rule_of(row.rule_key, row.enabled, row.params) for row in rows}  # type: ignore[arg-type]
    return RuleSet(**stored)  # type: ignore[arg-type]


def rule_out(key: RuleKey, rule: Rule) -> RuleOut:
    data = {"key": key, "name": RULE_NAMES[key], "enabled": rule.enabled, "params": params_of(rule)}
    return RULE_OUT.validate_python(data)


def list_rules(db: Session, community_id: uuid.UUID) -> list[RuleOut]:
    rules = load_rules(db, community_id)
    return [rule_out(key, getattr(rules, key)) for key in RULE_KEYS]


def update_rule(db: Session, community_id: uuid.UUID, key: RuleKey, update: RuleUpdate) -> RuleOut:
    """Apply a change; each field in `update.params` replaces the stored one. 422 when the
    thresholds it leaves are not valid."""
    row = db.scalar(
        select(RuleConfig)
        .where(RuleConfig.community_id == community_id, RuleConfig.rule_key == key)
        .with_for_update()
    )
    if row is None:
        default: Rule = getattr(RuleSet(), key)
        row = RuleConfig(
            id=rule_id(community_id, key),
            community_id=community_id,
            rule_key=key,
            params=params_of(default),
            enabled=default.enabled,
        )
        db.add(row)
    enabled = row.enabled if update.enabled is None else update.enabled
    try:
        rule = rule_of(key, enabled, {**row.params, **(update.params or {})})
    except ValidationError as error:
        name = RULE_NAMES[key].lower()
        details = error.errors(include_url=False, include_context=False)
        raise ApiError(
            422, "invalid_rule", f"The {name} thresholds are not valid", details
        ) from None
    row.enabled, row.params = enabled, params_of(rule)
    db.flush()
    return rule_out(key, rule)
