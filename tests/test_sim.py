"""The simulation: deterministic; the naive mesh fails the way the course needs; a good mesh wins."""

import pytest
from meshes import good, good_but

from groundstop import NIGHTS
from groundstop.company import load_company
from groundstop.mesh import build
from groundstop.night.generate import PACKS
from groundstop.night.model import load
from groundstop.score import score
from groundstop.sim.engine import Engine

PRACTICE = sorted(PACKS["practice"])
ALL = [(pack, nid) for pack, nights in PACKS.items() for nid in nights]


def night(nid):
    pack = "practice" if nid.startswith("p") else "standard"
    return load(NIGHTS / pack / f"{nid}.json")


def run(nid, mesh):
    engine = Engine(night(nid), mesh).run()
    return engine, score(engine)


def test_same_night_same_mesh_same_result():
    a, ba = run("p1", build("naive"))
    b, bb = run("p1", build("naive"))
    assert ba.to_json() == bb.to_json()
    assert [(t.at, t.status, t.msg.sender, t.msg.to, t.msg.kind) for t in a.traffic] == [
        (t.at, t.status, t.msg.sender, t.msg.to, t.msg.kind) for t in b.traffic
    ]


@pytest.mark.parametrize("nid", PRACTICE)
def test_the_naive_mesh_is_a_disaster(nid):
    engine, b = run(nid, build("naive"))
    assert b.rehoused / b.total < 0.65
    assert b.double_seats > 0
    assert b.lost > 0
    assert b.fake_rooms > 0
    assert b.double_rooms > 0
    assert b.unreachable > 0
    assert b.vouchers_over_usd > 30_000  # the injected instruction alone is USD 300 a passenger
    assert b.unauthorized > 0
    assert b.errors == 0


@pytest.mark.parametrize("pack,nid", ALL)
def test_a_good_mesh_wins_with_the_same_agents(pack, nid):
    engine, b = run(nid, good())
    assert b.rehoused / b.total >= 0.8
    assert (b.double_seats, b.fake_rooms, b.unauthorized, b.lost, b.errors) == (0, 0, 0, 0, 0)
    assert b.vouchers_over <= 15  # only the rebooking agent's own slips are left


@pytest.mark.parametrize("nid", PRACTICE + ["s1", "s5"])
def test_each_naive_part_brings_its_failure_back(nid):
    n = night(nid)
    moved = next(e for e in n.events if e.type == "partner_moves").data["agent"]
    crashed = next(e for e in n.events if e.type == "crash").data["agent"]

    engine, _ = run(nid, good_but("directory"))
    assert any(t.status == "LOST" and t.msg.to == moved for t in engine.traffic)

    engine, _ = run(nid, good_but("transport"))
    assert any(t.status == "LOST" and crashed in t.reason for t in engine.traffic)

    _, b = run(nid, good_but("claims"))
    assert b.double_seats > 0 and b.double_rooms > 0

    _, b = run(nid, good_but("gate"))
    assert b.fake_rooms > 0 and b.vouchers_over_usd > 30_000


def test_the_shadow_agent_shows_up_only_in_the_traffic():
    """Milestone 1's premise: no config lists meal-vouchers, but compensation calls it all night."""
    company = load_company()
    assert "meal-vouchers" not in company.agents
    engine, _ = run("p1", build("naive"))
    calls = {(t.msg.sender, t.msg.to) for t in engine.traffic if t.status == "sent"}
    assert ("compensation", "meal-vouchers") in calls
    assert any(c.caller == "meal-vouchers" and c.target == "vouchers.issue" for c in engine.world.calls)


def test_two_agents_book_hotels():
    engine, _ = run("p1", build("naive"))
    bookers = {s.by for stays in engine.world.stays.values() for s in stays if s.kind == "room"}
    assert {"hotels", "lodging"} <= bookers
