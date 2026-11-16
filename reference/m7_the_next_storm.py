"""Milestone 7, reference: a template, a factory, a four-gate pipeline and a retirement that checks first."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from typing import Any

from jsonschema import Draft202012Validator

from groundstop import COMPANY
from groundstop.company import load_company
from groundstop.factory import benchmark, calls_in, try_agent
from groundstop.logs import traffic
from groundstop.sdk import Agent, Ctx


class TemplateAgent(Agent):
    """The certified template: one kind of request in, its contract checked, one reply out, everything logged."""

    spec: dict[str, Any] = {}
    servers = 2
    default_service = 0.5

    @staticmethod
    def decide(body: dict, ctx: Ctx) -> dict:
        raise NotImplementedError

    def handle(self, msg, ctx: Ctx) -> None:
        spec = self.spec
        if msg.kind != spec["handles"]:
            ctx.log(f"ignored {msg.kind} from {msg.sender}: this agent only handles {spec['handles']}")
            return
        errors = list(Draft202012Validator(spec["input"]).iter_errors(msg.body))
        if errors:
            ctx.log(f"refused {msg.kind} from {msg.sender}: {errors[0].message}")
            return
        answer = type(self).decide(msg.body, ctx)
        ctx.log(f"{msg.kind} from {msg.sender}: {answer}")
        ctx.reply(msg, spec["replies"], answer)


def new_agent(spec: dict[str, Any], decide: Callable[[dict, Ctx], dict]) -> dict[str, Any]:
    """The factory: from a spec and a decision, an agent made from the template, with its contract and entry."""
    name = "".join(part.title() for part in spec["id"].split("-"))
    cls = type(name, (TemplateAgent,), {"id": spec["id"], "spec": spec, "decide": staticmethod(decide)})
    return {
        "id": spec["id"],
        "version": spec["version"],
        "team": spec["team"],
        "purpose": spec["purpose"],
        "address": f"http://{spec['id']}.{spec['team']}.fragata.internal:8080",
        "cls": cls,
        "needs": list(spec["needs"]),
        "tests": list(spec["tests"]),
        "contract": {
            "name": spec["id"], "version": spec["version"], "owner": spec["team"], "purpose": spec["purpose"],
            "type": "task-oriented", "input": spec["input"], "output": spec["output"], "limits": spec["limits"],
        },
    }  # fmt: skip


# ---- the agent Airport asked for -----------------------------------------------------------------

RULES = {int(k): v["may_enter"] for k, v in tomllib.loads((COMPANY / "entry-rules.toml").read_text())["groups"].items()}


def decide_entry(body: dict, ctx: Ctx) -> dict:
    p = ctx.call("reservations", "passenger", pax=body["pax"])
    rule = "yes" if p["local"] else RULES[p["passport_group"]]
    return {"pax": body["pax"], "may_enter": rule == "yes" or (rule == "with_visa" and p["visa"])}


def _tests() -> list[tuple[dict, dict]]:
    """One passenger of p1 for each case the rules have, with the answer the rules give."""
    import json

    from groundstop import NIGHTS

    people = json.loads((NIGHTS / "practice" / "p1.json").read_text())["passengers"]
    cases = [
        ("group 1", lambda p: p["passport_group"] == 1 and not p["local"], True),
        ("group 2 with a visa", lambda p: p["passport_group"] == 2 and p["visa"], True),
        ("group 2 without", lambda p: p["passport_group"] == 2 and not p["visa"], False),
        ("group 3", lambda p: p["passport_group"] == 3, False),
        ("lives in Panama", lambda p: p["local"], True),
    ]
    out = []
    for _, match, may in cases:
        p = next(p for p in people if match(p))
        out.append(({"pax": p["id"]}, {"pax": p["id"], "may_enter": may}))
    return out


ENTRY_RULES = {
    "id": "entry-rules",
    "version": "1.0.0",
    "team": "airport",
    "purpose": "Applies the entry rules: says whether a passenger in transit may leave the airport tonight, for a hotel.",
    "handles": "may_enter",
    "replies": "entry_decision",
    "input": {
        "type": "object",
        "required": ["pax"],
        "properties": {"pax": {"type": "string", "pattern": "^PX-[0-9]{5}$"}},
    },
    "output": {
        "type": "object",
        "required": ["pax", "may_enter"],
        "properties": {"pax": {"type": "string"}, "may_enter": {"type": "boolean"}},
    },
    "needs": ["reservations.passenger"],
    "limits": [
        "Answers only may_enter",
        "Reads a passenger's documents, changes nothing",
        "Applies company/entry-rules.toml as written",
    ],
    "tests": [],
}


def entry_rules() -> dict[str, Any]:
    return new_agent(dict(ENTRY_RULES, tests=_tests()), decide_entry)


# ---- the pipeline --------------------------------------------------------------------------------


def pipeline(candidate: dict[str, Any], registry: Any, trust: Any) -> dict[str, Any]:
    """Tests, benchmark, security scan, certification; registered only if all four pass. Stops at the first failure."""
    company = load_company()
    gates: list[dict[str, Any]] = []

    def gate(name: str, passed: bool, detail: str) -> bool:
        gates.append({"gate": name, "passed": passed, "detail": detail})
        return passed

    cls, spec = candidate["cls"], candidate["cls"].spec
    failures = []
    for body, want in candidate["tests"]:
        sent = try_agent(cls, spec["handles"], body)["sent"]
        if not sent or sent[0][1] != spec["replies"] or sent[0][2] != want:
            failures.append(f"{body} → {sent[0][2] if sent else 'nothing'}, expected {want}")
    if not gate(
        "tests",
        bool(candidate["tests"]) and not failures,
        failures[0] if failures else f"{len(candidate['tests'])} passed",
    ):
        return {"gates": gates, "registered": False}

    boards = benchmark(candidate)
    worse = [
        n
        for n, b in boards.items()
        if b["with"]["rehoused"] < b["without"]["rehoused"] or b["with"]["errors"] > b["without"]["errors"]
    ]
    if not gate("benchmark", not worse, f"worse on {', '.join(worse)}" if worse else "no night got worse"):
        return {"gates": gates, "registered": False}

    calls = calls_in(cls)
    allowed = {op for op, agents in company.scopes.items() if candidate["id"] in agents}
    extra = sorted(calls - set(candidate["needs"])) + sorted(set(candidate["needs"]) - allowed)
    if not gate(
        "security", not extra, f"calls or needs outside its policy: {extra}" if extra else f"calls only {sorted(calls)}"
    ):
        return {"gates": gates, "registered": False}

    record = trust.certify(
        candidate["id"],
        candidate["version"],
        by=company.first_with("certifier"),
        evidence={"tests": "passed", "gates": gates},
    )
    if not gate("certification", record is not None, "certified" if record else "the certifier refused"):
        return {"gates": gates, "registered": False}

    entry = {
        "id": candidate["id"], "version": candidate["version"], "owner": candidate["team"], "purpose": candidate["purpose"],
        "address": candidate["address"], "visibility": ["fragata"], "kind": "internal",
    }  # fmt: skip
    registered = registry.publish(entry, by=company.person_of(candidate["team"])) and registry.approve(
        candidate["id"], candidate["version"], by=company.first_with("reviewer")
    )
    return {"gates": gates, "registered": bool(registered)}


# ---- retirement ----------------------------------------------------------------------------------


def retire(agent: str, traffic_log: Any, registry: Any, trust: Any, by: str) -> dict[str, Any]:
    """Refuse while anyone still calls the agent; then retire it in the registry and revoke its certification."""
    callers = sorted({line.sender for line in traffic(traffic_log) if line.to == agent and line.sender != agent})
    if callers:
        return {"retired": False, "callers": callers}
    retired = registry.retire(agent, by=by)
    if retired:
        trust.revoke(agent, "retired", by=by)
    return {"retired": retired, "callers": []}


# ---- who decides what ----------------------------------------------------------------------------

DECISIONS = ("asks", "builds", "approves", "certifies", "on_call", "retires")


def operating_model() -> dict[str, str]:
    """Airport asks for it and builds it; the platform reviewer approves; the trust team certifies;
    the duty manager is woken up; Airport decides when it goes."""
    return {
        "asks": "jorge.pinto",
        "builds": "jorge.pinto",
        "approves": "lucia.mendez",
        "certifies": "tomas.herrera",
        "on_call": "carla.duarte",
        "retires": "jorge.pinto",
    }
