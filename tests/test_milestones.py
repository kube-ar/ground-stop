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


def test_m2_wrong_implementations_fail():
    ref = reference("2")

    def observer_contract():
        return dict(ref.contract(), type="observer")

    def plan_without_fare_rules(request):
        plan = ref.plan(request)
        steps = [s for s in plan["steps"] if s["run_by"] != "tool:fare_rules"]
        for s in steps:
            if s["run_by"] == "model:choose":
                s["parameters"]["options"] = {"from": "s1"}
            s["after"] = [a if a != "s2" else "s1" for a in s["after"]]
        return dict(plan, steps=steps)

    def contract_without_bags():
        c = ref.contract()
        c["input"] = dict(c["input"], required=[f for f in c["input"]["required"] if f != "has_bags"])
        c["input"]["properties"] = {k: v for k, v in c["input"]["properties"].items() if k != "has_bags"}
        return c

    def execute_without_sources(plan, tools):
        return [
            {**e, "parameters": {k: {"value": v["value"]} for k, v in e["parameters"].items()}}
            if "parameters" in e
            else e
            for e in ref.execute(plan, tools)
        ]

    def conforms_always_fine(plan, log):
        return []

    def conforms_counts_only(plan, log):
        steps = {s["id"] for s in plan["steps"]}
        return [] if {e["step"] for e in log} == steps else ["missing"]

    for fns, check in [
        ({"contract": observer_contract}, "The contract"),
        ({"plan": plan_without_fare_rules}, "A plan a program can check"),
        ({"contract": contract_without_bags}, "Called from the contract alone"),
        ({"execute": execute_without_sources}, "The log follows the plan"),
        ({"conforms": conforms_always_fine}, "Your conformance checker"),
        ({"conforms": conforms_counts_only}, "Your conformance checker"),
    ]:
        assert check in _failing("2", patched(ref, **fns)), check


def test_m3_wrong_workspaces_fail():
    ref = reference("3")

    class ForgetsOnCrash(ref.Workspace):
        def crashed(self, agent):
            while self.queue[agent]:
                self.env.lost(self.queue[agent].popleft(), f"{agent} crashed")
            self.reading.pop(agent, None)

    class DeliversOnlyWhenUp(ref.Workspace):
        def submit(self, msg):
            address = self.mesh.directory.resolve(msg.sender, msg.to)
            agent = self.env.who(address) if address else None
            if agent in self.outside or agent is None or self.env.is_up(agent):
                return super().submit(msg)
            self._remember(msg)
            self.env.lost(msg, f"connection refused: {agent} is down")

    class SaysYesToEveryone(ref.Workspace):
        def claim(self, caller, key):
            return True

    class NeverHandsOver(ref.Workspace):
        def _hand_over(self):
            pass

    class OnlyFragatasSide(ref.Workspace):
        def history(self, goal):
            outside = {"ondelia-rooms", "garoa-seats", "app", "sms-gateway"}
            return [e for e in super().history(goal) if e["sender"] not in outside]

    def with_workspace(cls):
        from groundstop.mesh import Mesh
        from groundstop.mesh.naive import NoIdentity, NoTracer, OpenGate, StaticDirectory

        def build():
            w = cls()
            return Mesh("wrong", StaticDirectory(), w, w, NoIdentity(), OpenGate(), NoTracer())

        return patched(ref, build=build)

    for cls, check in [
        (ForgetsOnCrash, "A crash loses no message"),
        (DeliversOnlyWhenUp, "A crash loses no message"),
        (SaysYesToEveryone, "Nothing is sold twice"),
        (NeverHandsOver, "Every case ends"),
        (OnlyFragatasSide, "Who did what"),
    ]:
        assert check in _failing("3", with_workspace(cls)), check


def test_m4_wrong_implementations_fail():
    ref = reference("4")

    class AnyoneApproves(ref.Registry):
        def approve(self, agent, version, by):
            pending = next((r for r in self.records if r["id"] == agent and r["version"] == version), None)
            if pending:
                for r in self.records:
                    if r["id"] == agent and r["status"] == "active":
                        r["status"] = "superseded"
                pending["status"] = "active"
            return self._note("approve", agent, version, by, pending is not None)

    class KeepsFirstAddress(ref.Registry):
        def resolve(self, caller, name):
            if name.startswith(("http://", "https://")):
                return name
            first = next((r for r in self.records if r["id"] == name and r["status"] in ("active", "superseded")), None)
            return first["address"] if first else None

    class AlwaysFindsSomeone(ref.Registry):
        def find(self, caller, purpose):
            want = ref.words(purpose)
            ranked = sorted(
                (r for r in self.records if r["status"] == "active" and r["id"] != caller),
                key=lambda r: -len(want & ref.words(r["purpose"])),
            )
            return ranked[0]["id"] if ranked else None

    class TraceEveryMessage(ref.Tracer):
        def stamp(self, msg, parent):
            msg.trace = f"T-{msg.id}"
            self.spans[msg.id] = {
                "id": msg.id,
                "parent": msg.parent,
                "sender": msg.sender,
                "to": msg.to,
                "kind": msg.kind,
                "sent_at": msg.sent_at,
                "handled_at": None,
                "trace": msg.trace,
            }
            self.order.setdefault(msg.trace, []).append(msg.id)
            if isinstance(msg.body.get("pax"), str):
                self.by_pax.setdefault(msg.body["pax"], msg.trace)

    class QueueTimeOnly(ref.Tracer):
        def slowest_hop(self, trace_id):
            spans = [s for s in self.trace(trace_id) if s["handled_at"] is not None]
            s = max(spans, key=lambda s: s["handled_at"] - s["sent_at"])
            return {"agent": s["to"], "seconds": s["handled_at"] - s["sent_at"]}

    for fns, check in [
        ({"Registry": AnyoneApproves}, "Publishing needs a review"),
        ({"Registry": KeepsFirstAddress}, "By name, not by address"),
        ({"Registry": AlwaysFindsSomeone}, "Discovery returns one agent"),
        ({"Tracer": TraceEveryMessage}, "One trace per passenger"),
        ({"Tracer": QueueTimeOnly}, "Where the time went"),
    ]:
        assert check in _failing("4", patched(ref, **fns)), check
