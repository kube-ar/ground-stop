"""Milestone 5, reference (fast path): HMAC-signed tokens from the standard library, and a gate over policies as data."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections import defaultdict
from typing import Any

from groundstop.company import load_company
from groundstop.mesh import ALLOW, Call, Decision, Env, Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoTracer, StaticDirectory

KEY = hashlib.sha256(b"fragata mesh signing key (a secret in real life)").digest()
LIFETIME = 3600.0
NEEDS_DELEGATION = {"app_hotel": "book_hotel"}  # messages that act for a passenger, and the scope they need


def policies() -> list[dict[str, Any]]:
    """company/scopes.toml, grouped: one policy per set of agents that share the same operations."""
    by_agents: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for op, agents in load_company().scopes.items():
        by_agents[tuple(sorted(agents))].append(op)
    owners = {"reservations": "customer", "crews": "operations", "sms": "customer", "vouchers": "customer"}
    out = []
    for i, (agents, ops) in enumerate(sorted(by_agents.items()), 1):
        system = ops[0].split(".")[0]
        out.append(
            {
                "id": f"P{i:02d}-{system}",
                "version": "1",
                "owner": owners.get(system, "airport"),
                "applies_to": list(agents),
                "allow": sorted(ops),
            }
        )
    return out


def _encode(claims: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode()
    sig = hmac.new(KEY, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _decode(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(KEY, body.encode(), hashlib.sha256).hexdigest()):
        return None
    return json.loads(base64.urlsafe_b64decode(body))


class Identity:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env = env
        company = load_company()
        self.known = set(company.agents) | set(company.gateways)
        self.revoked: set[str] = set()
        self.issued: dict[str, tuple[str, float]] = {}

    def credential(self, agent: str) -> str | None:
        if agent not in self.known or agent in self.revoked:
            return None
        token, expires = self.issued.get(agent, (None, 0.0))
        if token is None or expires - self.env.now < 300:  # rotate before it runs out
            expires = self.env.now + LIFETIME
            token = _encode({"agent": agent, "expires": expires, "type": "agent"})
            self.issued[agent] = (token, expires)
        return token

    def verify(self, credential: str | None) -> dict[str, Any] | None:
        claims = _decode(credential)
        if not claims or claims.get("type") != "agent":
            return None
        if claims["agent"] in self.revoked or claims["expires"] <= self.env.now:
            return None
        return claims

    def revoke(self, agent: str) -> None:
        self.revoked.add(agent)
        self.issued.pop(agent, None)

    def delegate(self, agent: str, pax: str, scope: list[str], ttl: float) -> str:
        return _encode(
            {"agent": agent, "pax": pax, "scope": list(scope), "expires": self.env.now + ttl, "type": "delegation"}
        )

    def verify_delegation(self, token: str | None) -> dict[str, Any] | None:
        claims = _decode(token)
        if not claims or claims.get("type") != "delegation" or claims["expires"] <= self.env.now:
            return None
        return claims


class Gate:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        self.allow: dict[str, set[str]] = defaultdict(set)
        for policy in policies():
            for agent in policy["applies_to"]:
                self.allow[agent].update(policy["allow"])

    def check(self, call: Call) -> Decision:
        identity = self.mesh.identity
        if call.credential is None:
            return Decision(False, f"unknown caller {call.caller}: no credential")
        if call.caller in getattr(identity, "revoked", set()):
            return Decision(False, f"{call.caller} has been revoked")
        claims = identity.verify(call.credential)
        if claims is None:
            return Decision(False, f"{call.caller}'s credential is forged or expired")
        if claims["agent"] != call.caller:
            return Decision(False, f"the credential belongs to {claims['agent']}, not {call.caller}")
        if call.kind == "system":
            if call.target in self.allow.get(call.caller, set()):
                return ALLOW
            return Decision(False, f"no policy lets {call.caller} call {call.target}")
        scope = NEEDS_DELEGATION.get(call.action)
        if scope:
            grant = identity.verify_delegation(call.delegation)
            if grant is None:
                return Decision(False, f"{call.action} acts for a passenger: its delegation is missing or expired")
            if grant["pax"] != call.body.get("pax") or scope not in grant["scope"] or grant["agent"] != call.caller:
                return Decision(False, f"the delegation doesn't cover {scope} for {call.body.get('pax')}")
        return ALLOW


def build() -> Mesh:
    return Mesh("zero-trust", StaticDirectory(), DirectTransport(), NoClaims(), Identity(), Gate(), NoTracer())
