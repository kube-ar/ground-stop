"""Milestone checks: the starters aren't started, the references pass, and wrong answers fail."""

import importlib
import importlib.util
import types
from pathlib import Path

import pytest

from groundstop import ROOT
from groundstop.cli import main
from groundstop.milestones import MILESTONES


def reference(mid: str) -> types.ModuleType:
    m = MILESTONES[mid]
    spec = importlib.util.spec_from_file_location(f"ref_m{mid}", ROOT / m.reference)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checks(mid: str):
    return importlib.import_module(MILESTONES[mid].checks)


def patched(module: types.ModuleType, **fns) -> types.ModuleType:
    copy = types.ModuleType(module.__name__ + "_wrong")
    copy.__dict__.update(module.__dict__)
    copy.__dict__.update(fns)
    return copy


@pytest.fixture(scope="module", autouse=True)
def replayed():
    main(["replay", "p1"])  # milestone 0 checks that you ran it


@pytest.mark.parametrize("mid", sorted(MILESTONES))
def test_starter_is_not_started(mid):
    starter = importlib.import_module(MILESTONES[mid].module)
    results = checks(mid).run(starter)
    answers = [r for r in results if r.lesson is not None]
    assert answers and all(not r.started for r in answers)


@pytest.mark.parametrize("mid", sorted(MILESTONES))
def test_reference_passes(mid):
    results = checks(mid).run(reference(mid))
    assert all(r.passed for r in results), [(r.name["en"], r.details) for r in results if not r.passed]


def _failing(mid, module) -> set[str]:
    return {r.name["en"] for r in checks(mid).run(module) if not r.passed}


def test_m0_wrong_answers_fail():
    good = reference("0").answers()
    one_holder = dict(good, seat_sold_twice=dict(good["seat_sold_twice"], seat="30F"))
    wrong_pax = dict(good, seat_sold_twice=dict(good["seat_sold_twice"], passengers=["PX-48055", "PX-00000"]))
    staffed = dict(good, never_reached_crew="F950+1")
    off_by_one = dict(good, rehoused=good["rehoused"] + 1)
    for answers, check in [
        (one_holder, "A seat sold twice"),
        (wrong_pax, "A seat sold twice"),
        (staffed, "The message crew never got"),
        (off_by_one, "You read the scoreboard"),
    ]:
        module = types.SimpleNamespace(answers=lambda a=answers: a)
        assert check in _failing("0", module)


def test_m1_wrong_implementations_fail():
    from groundstop.logs import is_address, system_calls, traffic

    ref = reference("1")

    def seen_with_gateways(path):
        names = set()
        for line in traffic(path):
            names.add(line.sender)
            if not is_address(line.to):
                names.add(line.to)
        return names

    def links_ordered(path):
        gateways = {"weather", "app", "sms-gateway"}
        return len(
            {
                (x.sender, x.to)
                for x in traffic(path)
                if x.sender not in gateways and x.to not in gateways and not is_address(x.to)
            }
        )

    def overlaps_with_reads(path):
        by_op = {}
        for line in system_calls(path):
            by_op.setdefault(line.target, set()).add(line.caller)
        return {op: agents for op, agents in by_op.items() if len(agents) > 1}

    def declared_teams_only(company):
        return {k: v for k, v in ref.declared(company).items() if v != "partner"}

    def unlisted_inside_only(company, t, s):
        return {k: "inside" for k in ref.unlisted(company, t, s)}

    for fns, check in [
        ({"seen": seen_with_gateways}, "What the traffic shows"),
        ({"links": links_ordered}, "Pairs that talk directly"),
        ({"overlaps": overlaps_with_reads}, "Jobs two agents do"),
        ({"declared": declared_teams_only}, "What the configs declare"),
        ({"unlisted": unlisted_inside_only}, "The agents nobody listed"),
    ]:
        assert check in _failing("1", patched(ref, **fns)), check


def test_log_readers_read_every_line(tmp_path: Path):
    from groundstop.logs import system_calls, traffic

    main(["replay", "p2", "--out", str(tmp_path)])
    for path, reader in [(tmp_path / "traffic.log", traffic), (tmp_path / "systems.log", system_calls)]:
        assert len(reader(path)) == len(path.read_text(encoding="utf-8").splitlines())
