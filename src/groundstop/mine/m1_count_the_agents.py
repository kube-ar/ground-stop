"""Milestone 1, count the agents: who really runs at Fragata, by the configs and by the traffic.

Fast path: `groundstop.company.load_company()` reads the configs and `groundstop.logs` reads the
logs. Deep path: read company/*.toml with `tomllib` and parse the log lines yourself.

Check: `uv run ground-stop check 1`. It replays two nights and runs these functions on their logs.
Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/count-the-agents
"""

from __future__ import annotations

from pathlib import Path

# Operations that change something. The others (manifest, seat_map, passenger…) only read.
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
    """Every agent the configs declare, with its team's id ("partner" for a partner's agent).

    The configs are company/teams/*.toml and company/partners.toml. The gateways in
    company/gateways.toml send messages too, but they're systems, not agents.
    """
    raise NotImplementedError


def seen(traffic: Path) -> set[str]:
    """Every agent that sent or received a message in this traffic.log, by name.

    Skip recipients written as an address (http://… or https://…), and leave out the gateways.
    """
    raise NotImplementedError


def unlisted(company: Path, traffic: Path, systems: Path) -> dict[str, str]:
    """Agents the traffic shows but no config declares, each marked "inside" if it called one of
    Fragata's systems (systems.log) or "outside" if it never did."""
    raise NotImplementedError


def overlaps(systems: Path) -> dict[str, set[str]]:
    """For each operation in CHANGES that two or more agents performed (status ok), who did it."""
    raise NotImplementedError


def links(traffic: Path) -> int:
    """How many pairs of agents talked to each other directly: each pair counted once, whoever wrote
    first, with the same rules as seen()."""
    raise NotImplementedError
