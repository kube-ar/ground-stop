"""Fragata as the configs describe it: teams, their agents, partners, gateways and rules.

This is what the teams wrote down. It isn't the whole truth: the traffic of a real night shows
calls no config mentions.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import cache

from . import COMPANY


@dataclass(frozen=True)
class AgentSpec:
    id: str
    team: str  # team id, or "partner"
    purpose: dict[str, str]
    address: str
    calls: dict[str, str] = field(default_factory=dict)  # name → the address its code has hardcoded
    publishes: dict[str, list[str]] = field(default_factory=dict)  # topic → who its code tells
    outside: bool = False  # a partner's agent, run by another company


@dataclass(frozen=True)
class Company:
    teams: dict[str, dict[str, str]]  # team id → name per language
    agents: dict[str, AgentSpec]  # every agent some config declares
    gateways: dict[str, AgentSpec]  # systems that send messages to agents (weather, app, SMS replies)
    scopes: dict[str, list[str]]  # "system.op" → agents allowed to call it
    policy: dict[str, int]
    people: dict[str, dict[str, str]] = field(default_factory=dict)  # person → {"team", "role"}

    def person_of(self, team: str, role: str = "developer") -> str:
        """The first person of a team with a role (who publishes that team's agents, say)."""
        return next(p for p, info in self.people.items() if info["team"] == team and info["role"] == role)

    def first_with(self, role: str) -> str:
        return next(p for p, info in self.people.items() if info["role"] == role)


def _read(name: str) -> dict:
    return tomllib.loads((COMPANY / name).read_text(encoding="utf-8"))


def _spec(raw: dict, team: str, outside: bool = False) -> AgentSpec:
    return AgentSpec(
        id=raw["id"],
        team=team,
        purpose=raw["purpose"],
        address=raw.get("address", ""),
        calls=dict(raw.get("calls", {})),
        publishes={k: list(v) for k, v in raw.get("publishes", {}).items()},
        outside=outside,
    )


@cache
def load_company() -> Company:
    teams: dict[str, dict[str, str]] = {}
    agents: dict[str, AgentSpec] = {}
    for path in sorted((COMPANY / "teams").glob("*.toml")):
        data = _read(f"teams/{path.name}")
        teams[data["id"]] = data["name"]
        for raw in data.get("agents", []):
            agents[raw["id"]] = _spec(raw, data["id"])
    for raw in _read("partners.toml")["agents"]:
        agents[raw["id"]] = _spec(raw, "partner", outside=True)
    gateways = {raw["id"]: _spec(raw, "gateway") for raw in _read("gateways.toml")["gateways"]}
    return Company(
        teams=teams,
        agents=agents,
        gateways=gateways,
        scopes=_read("scopes.toml")["systems"],
        policy=_read("compensation-policy.toml"),
        people={p["id"]: {"team": p["team"], "role": p["role"]} for p in _read("people.toml")["people"]},
    )


@cache
def _entry_rules() -> dict[int, str]:
    return {int(k): v["may_enter"] for k, v in _read("entry-rules.toml")["groups"].items()}


def can_enter(passenger) -> bool:
    """May this passenger leave the airport tonight? (company/entry-rules.toml; fictional rules)"""
    if passenger.local:
        return True
    rule = _entry_rules()[passenger.passport_group]
    return rule == "yes" or (rule == "with_visa" and passenger.visa)


def entitlement(delay_hours: float | None) -> list[tuple[str, int]]:
    """The vouchers the policy gives one passenger, given how late their new flight leaves."""
    policy = load_company().policy
    due = [("meal", policy["meal_voucher_usd"])]
    if delay_hours is not None and delay_hours > policy["long_delay_hours"]:
        due.append(("long_delay", policy["long_delay_usd"]))
    return due
