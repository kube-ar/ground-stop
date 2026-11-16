"""The nights: reproducible from their seeds, and winnable by construction."""

from collections import Counter

import pytest

from groundstop import NIGHTS
from groundstop.company import can_enter, load_company
from groundstop.night.generate import PACKS, generate
from groundstop.night.model import Night, load
from groundstop.night.places import DESTINATIONS

ALL = [(pack, nid) for pack, nights in PACKS.items() for nid in nights]


@pytest.mark.parametrize("pack,nid", ALL)
def test_files_match_their_seeds(pack, nid):
    on_disk = load(NIGHTS / pack / f"{nid}.json")
    assert on_disk.to_json() == generate(nid, pack, PACKS[pack][nid]).to_json()


def test_round_trip():
    night = generate("x", "practice", 1)
    assert Night.from_json(night.to_json()).to_json() == night.to_json()


def test_different_seeds_give_different_nights():
    a, b = generate("a", "practice", 1), generate("b", "practice", 2)
    assert [f.dest for f in a.cancelled] != [f.dest for f in b.cancelled]


@pytest.mark.parametrize("pack,nid", ALL)
def test_every_passenger_can_get_a_seat(pack, nid):
    night = load(NIGHTS / pack / f"{nid}.json")
    stranded = Counter(p.dest for p in night.passengers)
    interline = Counter(p.dest for p in night.passengers if p.interline)
    for dest, count in stranded.items():
        own = sum(
            f.capacity if f.kind == "extra" else len(f.free_seats)
            for f in night.flights
            if f.airline == "fragata" and f.kind != "cancelled" and f.dest == dest
        )
        partner = sum(len(f.free_seats) for f in night.flights if f.airline == "garoa" and f.dest == dest)
        assert own + min(partner, interline[dest]) >= count, dest


@pytest.mark.parametrize("pack,nid", ALL)
def test_without_one_extra_flight_someone_has_no_seat(pack, nid):
    """Losing a crew must cost seats: the day after can't absorb a whole extra flight."""
    night = load(NIGHTS / pack / f"{nid}.json")
    for extra in (f for f in night.flights if f.kind == "extra"):
        later = sum(len(f.free_seats) for f in night.flights if f.dest == extra.dest and f.id.endswith("+2"))
        assert later < extra.capacity


@pytest.mark.parametrize("pack,nid", ALL)
def test_the_night_has_every_trap(pack, nid):
    night = load(NIGHTS / pack / f"{nid}.json")
    types = [e.type for e in night.events]
    assert sorted(types) == ["crash", "ground_stop", "injection", "intruder", "partner_moves"]
    assert [e.at for e in night.events] == sorted(e.at for e in night.events)
    eligible = sum(1 for p in night.passengers if not p.local and can_enter(p))
    assert sum(h.rooms for h in night.hotels) < eligible  # not enough rooms for everyone
    assert night.airside_care >= sum(1 for p in night.passengers if not p.local)
    assert any(h.seconds_per_booking >= 60 for h in night.hotels)  # one slow hotel


def test_places_and_rules():
    assert {"PTY"} - set(DESTINATIONS) == {"PTY"}
    company = load_company()
    assert len(company.teams) == 5
    internal = [a for a in company.agents.values() if not a.outside]
    partners = [a for a in company.agents.values() if a.outside]
    assert len(internal) + len(partners) == 11 and len(partners) == 2
    planned = {"entry-rules"}  # the agent milestone 7 builds; its policy is ready before it is
    for target, agents in company.scopes.items():
        assert all(a in company.agents or a in planned for a in agents), target
