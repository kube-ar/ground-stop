"""Milestone 7, the next storm: a factory for new agents, a pipeline every agent passes, and a safe way out.

Airport asked for an agent nobody has: one that says whether a passenger in transit may leave the
airport for a hotel. `hotels` already asks discovery for one every time it needs a bed. You build
it the way a company with many agents should: from a template, through a pipeline of gates, into
the registry. Then you retire the hotel agent nobody should have built twice.

The platform's kit (groundstop/factory.py): try_agent() runs one message through an agent in a
sandbox; benchmark() replays practice nights with and without a new agent; calls_in() reads which
systems an agent's code calls.

Check: `uv run ground-stop check 7`.
Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/the-next-storm
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from groundstop.sdk import Agent, Ctx


class TemplateAgent(Agent):
    """The template every new agent starts from: one kind of request in, checked against the
    contract's input, one reply out, and a line in the agent's log for each. A new agent only
    brings its spec and its decision."""

    spec: dict[str, Any] = {}

    @staticmethod
    def decide(body: dict, ctx: Ctx) -> dict:
        raise NotImplementedError

    def handle(self, msg, ctx: Ctx) -> None:
        raise NotImplementedError


def new_agent(spec: dict[str, Any], decide: Callable[[dict, Ctx], dict]) -> dict[str, Any]:
    """The factory. From a spec (see ENTRY_RULES) and a decision function, a candidate:
    {"id", "version", "team", "purpose", "address", "cls" (a TemplateAgent subclass), "needs",
    "tests", "contract"}."""
    raise NotImplementedError


ENTRY_RULES: dict[str, Any] = {
    "id": "entry-rules",
    "version": "1.0.0",
    "team": "airport",
    "purpose": "",  # write one discovery will match: hotels searches for what it needs
    "handles": "may_enter",  # hotels sends {"pax": ...}
    "replies": "entry_decision",  # hotels expects {"pax": ..., "may_enter": true or false}
    "input": {},  # JSON Schemas
    "output": {},
    "needs": [],  # the system operations it calls
    "limits": [],
    "tests": [],  # (request body, expected reply body) pairs
}


def entry_rules() -> dict[str, Any]:
    """The entry-rules agent, from the factory: company/entry-rules.toml applied to a passenger's documents."""
    raise NotImplementedError


def pipeline(candidate: dict[str, Any], registry: Any, trust: Any) -> dict[str, Any]:
    """Every new agent passes the same gates, in order: tests, benchmark, security, certification.
    Register it (publish, then approve) only if all four pass. Return
    {"gates": [{"gate", "passed", "detail"}, ...], "registered": bool}."""
    raise NotImplementedError


def retire(agent: str, traffic: Any, registry: Any, trust: Any, by: str) -> dict[str, Any]:
    """Retire an agent safely: refuse while anything in `traffic` (a traffic.log) still calls it;
    otherwise retire it in the registry and revoke its certification, keeping its history.
    Return {"retired": bool, "callers": [...]}."""
    raise NotImplementedError
