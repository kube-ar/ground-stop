"""Milestone 1, reference (fast path): the configs through load_company(), the logs through groundstop.logs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from groundstop.company import load_company
from groundstop.logs import is_address, system_calls, traffic

CHANGES = (
    "reservations.cancel",
    "reservations.assign",
    "reservations.record_partner",
    "crews.assign",
    "sms.send",
    "vouchers.issue",
    "care.reserve",
    "stays.record",
    "bags.retag",
)


def declared(company: Path) -> dict[str, str]:
    return {a.id: ("partner" if a.outside else a.team) for a in load_company().agents.values()}


def _gateways() -> set[str]:
    return set(load_company().gateways)


def seen(traffic_log: Path) -> set[str]:
    gateways = _gateways()
    names = set()
    for line in traffic(traffic_log):
        names.add(line.sender)
        if not is_address(line.to):
            names.add(line.to)
    return names - gateways


def unlisted(company: Path, traffic_log: Path, systems: Path) -> dict[str, str]:
    callers = {line.caller for line in system_calls(systems)}
    unknown = seen(traffic_log) - set(declared(company))
    return {name: ("inside" if name in callers else "outside") for name in unknown}


def overlaps(systems: Path) -> dict[str, set[str]]:
    by_op = defaultdict(set)
    for line in system_calls(systems):
        if line.target in CHANGES and line.status == "ok":
            by_op[line.target].add(line.caller)
    return {op: agents for op, agents in by_op.items() if len(agents) > 1}


def links(traffic_log: Path) -> int:
    gateways = _gateways()
    pairs = set()
    for line in traffic(traffic_log):
        if line.sender in gateways or line.to in gateways or is_address(line.to) or line.sender == line.to:
            continue
        pairs.add(frozenset((line.sender, line.to)))
    return len(pairs)
