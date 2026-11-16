"""Milestone 2, reference: a contract, a nine-step plan, an executor that logs, and a conformance check."""

from __future__ import annotations

from collections import Counter
from typing import Any

AGENT = "rebooking@2.0.0"


def contract() -> dict[str, Any]:
    nullable = {"type": ["string", "null"]}
    return {
        "name": "rebooking",
        "version": "2.0.0",
        "owner": "customer",
        "purpose": "Finds a passenger of a cancelled flight a new flight to their own city, books it, and tells "
        "messaging, baggage, hotels and compensation what they need to know.",
        "type": "task-oriented",
        "input": {
            "type": "object",
            "required": ["pax", "dest", "booked_dep", "interline", "has_bags", "needs_night"],
            "properties": {
                "pax": {"type": "string", "pattern": "^PX-[0-9]{5}$"},
                "dest": {"type": "string", "pattern": "^[A-Z]{3}$"},
                "booked_dep": {"type": "integer", "description": "when the cancelled flight was due to leave"},
                "interline": {"type": "boolean", "description": "the fare allows a partner's seat"},
                "has_bags": {"type": "boolean"},
                "needs_night": {"type": "boolean", "description": "not from Panama, and no night arranged yet"},
            },
        },
        "output": {
            "type": "object",
            "required": ["status", "booked", "flight", "seat", "dep"],
            "properties": {
                "status": {"enum": ["booked", "waiting", "no_seat"]},
                "booked": {"type": "boolean"},
                "flight": nullable,
                "seat": nullable,
                "dep": {"type": ["integer", "null"]},
            },
        },
        "limits": [
            "Only flights to the passenger's own city",
            "A partner's seat only with an interline fare",
            "One seat per passenger: a new booking replaces the old one",
            "Waits for an extra flight until 04:00, then books the day after",
        ],
    }


def plan(request: dict[str, Any]) -> dict[str, Any]:
    def ask(source: str) -> dict:
        return {"from": source}

    pax = ask("request.pax")
    steps = [
        {"id": "s1", "run_by": "tool:find_flights", "parameters": {"dest": ask("request.dest")}, "after": []},
        {
            "id": "s2",
            "run_by": "tool:fare_rules",
            "parameters": {"flights": ask("s1"), "interline": ask("request.interline")},
            "after": ["s1"],
        },
        {"id": "s3", "run_by": "model:choose", "parameters": {"options": ask("s2")}, "after": ["s2"]},
        {"id": "s4", "run_by": "tool:book_seat", "parameters": {"pax": pax, "option": ask("s3")}, "after": ["s3"]},
        {
            "id": "s5",
            "run_by": "agent:messaging",
            "parameters": {"pax": pax, "flight": ask("s4.flight"), "seat": ask("s4.seat"), "dep": ask("s4.dep")},
            "after": ["s4"],
            "only_if": ["s4.booked"],
        },
        {
            "id": "s6",
            "run_by": "agent:baggage",
            "parameters": {"pax": pax, "flight": ask("s4.flight")},
            "after": ["s4"],
            "only_if": ["s4.booked", "request.has_bags"],
        },
        {
            "id": "s7",
            "run_by": "agent:hotels",
            "parameters": {"pax": pax, "dep": ask("s4.dep")},
            "after": ["s4"],
            "only_if": ["request.needs_night", "s4.dep"],
        },
        {
            "id": "s8",
            "run_by": "tool:delay_hours",
            "parameters": {"dep": ask("s4.dep"), "booked_dep": ask("request.booked_dep")},
            "after": ["s4"],
            "only_if": ["s4.booked"],
        },
        {
            "id": "s9",
            "run_by": "agent:compensation",
            "parameters": {"pax": pax, "delay_hours": ask("s8")},
            "after": ["s8"],
            "only_if": ["s4.booked"],
        },
    ]
    return {"task_id": f"rebook:{request['pax']}", "agent": AGENT, "request": request, "steps": steps}


def _source(ref: str, request: dict, results: dict, now: float) -> Any:
    root, _, field = ref.partition(".")
    if root == "request":
        return request[field]
    if root == "clock":
        return now
    result = results.get(root)
    if field:
        return result.get(field) if isinstance(result, dict) else None
    return result


def execute(plan: dict[str, Any], tools: Any) -> list[dict[str, Any]]:
    request, results, log = plan["request"], {}, []
    for step in plan["steps"]:
        entry = {"step": step["id"], "run_by": step["run_by"], "at": tools.now}
        unmet = [c for c in step.get("only_if", []) if not _source(c, request, results, tools.now)]
        if unmet:
            log.append(entry | {"status": "skipped", "reason": f"only_if: {unmet[0]} doesn't hold"})
            continue
        parameters = {}
        for name, spec in step["parameters"].items():
            if isinstance(spec, dict) and "from" in spec:
                parameters[name] = {"value": _source(spec["from"], request, results, tools.now), "from": spec["from"]}
            else:
                parameters[name] = {"value": spec, "from": "literal"}
        try:
            result = tools.call(step["run_by"], {k: v["value"] for k, v in parameters.items()})
        except Exception as e:
            log.append(entry | {"status": "failed", "parameters": parameters, "error": str(e)})
            break
        results[step["id"]] = result
        log.append(entry | {"status": "done", "parameters": parameters, "result": result})
    return log


def conforms(plan: dict[str, Any], log: list[dict[str, Any]]) -> list[str]:
    problems = []
    steps = {s["id"]: s for s in plan["steps"]}
    count = Counter(e["step"] for e in log)
    for sid, step in steps.items():
        if count[sid] == 0 and not any(e["status"] == "failed" for e in log):
            problems.append(f"{sid} ({step['run_by']}) is in the plan but not in the log")
    for sid, n in count.items():
        if sid not in steps:
            problems.append(f"{sid} is in the log but not in the plan")
        elif n > 1:
            problems.append(f"{sid} ran {n} times")
    position = {}
    for i, e in enumerate(log):
        position.setdefault(e["step"], i)
    for sid, step in steps.items():
        for before in step.get("after", []):
            if sid in position and before in position and position[before] > position[sid]:
                problems.append(f"{sid} ran before {before}, which it waits for")
    request, results = plan["request"], {}
    for e in log:
        step = steps.get(e["step"])
        if step is None:
            continue
        should_run = all(_source(c, request, results, e.get("at", 0)) for c in step.get("only_if", []))
        if e["status"] == "skipped" and should_run:
            problems.append(f"{e['step']} was skipped, but its only_if held")
        if e["status"] == "done" and not should_run:
            problems.append(f"{e['step']} ran, but its only_if didn't hold")
        if e["status"] == "done":
            for name, spec in step["parameters"].items():
                logged = e.get("parameters", {}).get(name, {})
                source = spec["from"] if isinstance(spec, dict) and "from" in spec else "literal"
                expected = spec if source == "literal" else _source(source, request, results, e.get("at", 0))
                if logged.get("from") != source:
                    problems.append(f"{e['step']}.{name} came from {logged.get('from')!r}, the plan says {source!r}")
                elif source != "clock" and logged.get("value") != expected:
                    problems.append(f"{e['step']}.{name} isn't the value at {source}")
            results[e["step"]] = e.get("result")
    return problems
