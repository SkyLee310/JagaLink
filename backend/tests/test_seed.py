from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Link, Node, RuleConfig, Scenario
from app.db.seed import SeedReport, seed, seed_id


def node_by_code(db: Session, code: str) -> Node:
    return db.scalars(select(Node).where(Node.code == code)).one()


def test_seed_loads_taman_simulasi(seeded: SeedReport) -> None:
    assert seeded.created
    assert (seeded.zones, seeded.nodes, seeded.links, seeded.users) == (6, 20, 23, 4)
    assert (seeded.scenarios, seeded.rules) == (2, 3)
    assert seeded.community_id == seed_id("taman-simulasi", "community")


def test_seed_twice_same_rows(db: Session, seeded: SeedReport) -> None:
    again = seed(db)
    assert not again.created
    assert (again.zones, again.nodes, again.links, again.users) == (
        seeded.zones,
        seeded.nodes,
        seeded.links,
        seeded.users,
    )


def test_seed_leaves_edits_alone(db: Session, seeded: SeedReport) -> None:
    node = node_by_code(db, "c-main-02")
    edited_x = node.x + 100
    node.x = edited_x
    db.flush()
    seed(db)
    assert db.scalar(select(Node.x).where(Node.code == "c-main-02")) == edited_x


def test_reset_restores_layout(db: Session, seeded: SeedReport) -> None:
    node = node_by_code(db, "c-main-02")
    original_x = node.x
    node.x += 100
    db.execute(delete(Link).where(Link.from_node_id == node.id))
    db.flush()

    report = seed(db, reset=True)

    assert report == seeded
    assert node_by_code(db, "c-main-02").x == original_x


def test_guards_stand_at_their_nodes(db: Session, seeded: SeedReport) -> None:
    guard_b = db.scalars(select(AppUser).where(AppUser.code == "u-guard-02")).one()
    assert guard_b.current_node_id == seed_id("taman-simulasi", "node", "c-main-02")


def test_scenarios_follow_their_files(db: Session, seeded: SeedReport) -> None:
    s1 = db.get(Scenario, seed_id("taman-simulasi", "scenario", "s1-evening-vehicle"))
    assert s1 is not None
    assert (s1.script_path, s1.duration_s) == ("s1-evening-vehicle.json", 14 * 60)
    s1.name = "renamed"
    db.delete(db.get(Scenario, seed_id("taman-simulasi", "scenario", "s2-night-fence")))
    db.flush()

    again = seed(db)

    assert again.scenarios == 2
    assert s1.name == "S1 · Vehicle circling the south lanes"


def rule(db: Session, key: str) -> RuleConfig | None:
    return db.scalars(select(RuleConfig).where(RuleConfig.rule_key == key)).one_or_none()


def test_rules_start_at_the_engine_defaults_and_keep_their_edits(
    db: Session, seeded: SeedReport
) -> None:
    loiter = rule(db, "loiter")
    assert loiter is not None
    assert loiter.params == {"threshold_s": 180.0, "window_s": 600.0, "severity": "medium"}
    loiter.params = {**loiter.params, "threshold_s": 60.0}
    db.execute(delete(RuleConfig).where(RuleConfig.rule_key == "off_route"))
    db.flush()

    again = seed(db)

    assert again.rules == 3
    assert db.scalar(select(RuleConfig.params).where(RuleConfig.rule_key == "loiter")) == {
        "threshold_s": 60.0,
        "window_s": 600.0,
        "severity": "medium",
    }
    restored = rule(db, "off_route")
    assert restored is not None and restored.params == {"severity": "high"}
