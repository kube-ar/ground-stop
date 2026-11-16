"""Milestone 6, reference (fast path): certifications in a list, caps from the policy, strikes in a window."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from groundstop.company import load_company
from groundstop.mesh import ALLOW, Call, Decision, Env, Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, NoTracer, OpenGate, StaticDirectory

CAPS = {"meal": 15, "long_delay": 200}
VALID_FOR = 365 * 86_400.0
STRIKES = 5  # calls against the policy...
WINDOW = 600.0  # ...within ten minutes, and the agent is out of character


class TrustGate:
    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        bind = getattr(self.inner, "bind", None)
        if bind:
            bind(env, mesh)
        company = load_company()
        self.people = company.people
        self.agents = set(company.agents)
        self.duty = company.first_with("duty")
        self.records: list[dict[str, Any]] = []
        self.strikes: dict[str, list[float]] = defaultdict(list)
        self.given: set[tuple[str, str]] = set()
        self.told: list[dict[str, Any]] = []

    # certifications

    def certify(self, agent: str, version: str, by: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
        if self.people.get(by, {}).get("role") != "certifier" or evidence.get("tests") != "passed":
            return None
        for r in self.records:
            if r["agent"] == agent and r["status"] == "active":
                r["status"] = "superseded"
        record = {
            "agent": agent, "version": version, "issued_by": by, "issued": self.env.now,
            "expires": self.env.now + VALID_FOR, "status": "active", "evidence": dict(evidence),
        }  # fmt: skip
        self.records.append(record)
        return dict(record)

    def _valid(self, agent: str) -> dict[str, Any] | None:
        version = self.env.version_of(agent) if hasattr(self.env, "version_of") else None
        for r in reversed(self.records):
            if r["agent"] == agent and r["status"] == "active" and r["expires"] > self.env.now:
                if version is None or r["version"] == version:
                    return r
        return None

    def revoke(self, agent: str, reason: str, by: str) -> bool:
        record = self._valid(agent) or next(
            (r for r in reversed(self.records) if r["agent"] == agent and r["status"] == "suspended"), None
        )
        if record is None:
            return False
        record["status"], record["reason"] = "revoked", reason
        return True

    def certifications(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.records]

    def may_resume(self, agent: str) -> bool:
        return self._valid(agent) is not None

    def alerts(self) -> list[dict[str, Any]]:
        return list(self.told)

    # the decision

    def _strike(self, agent: str, reason: str) -> Decision:
        now = self.env.now
        recent = [t for t in self.strikes[agent] if now - t <= WINDOW] + [now]
        self.strikes[agent] = recent
        if len(recent) >= STRIKES and self._valid(agent):
            record = self._valid(agent)
            record["status"], record["reason"] = "suspended", f"out of character: {reason}"
            self.told.append({"at": now, "agent": agent, "reason": reason, "to": self.duty})
            self.env.quarantine(agent, reason)
        return Decision(False, reason)

    def check(self, call: Call) -> Decision:
        decision = self.inner.check(call)
        if not decision.allowed:
            return decision
        if call.caller in self.agents and self._valid(call.caller) is None:
            return Decision(False, f"{call.caller} has no valid certification for the version it runs")
        if call.kind == "system" and call.target == "vouchers.issue":
            kind, amount, pax = call.body.get("kind"), call.body.get("amount", 0), call.body.get("pax")
            if kind not in CAPS:
                return self._strike(call.caller, f"a {kind} voucher isn't in the compensation policy")
            if amount > CAPS[kind]:
                return self._strike(call.caller, f"USD {amount} is over the policy's {CAPS[kind]} for a {kind} voucher")
            if (pax, kind) in self.given:
                return self._strike(call.caller, f"{pax} already got a {kind} voucher")
            self.given.add((pax, kind))
        return ALLOW


def build() -> Mesh:
    return Mesh(
        "trust", StaticDirectory(), DirectTransport(), NoClaims(), NoIdentity(), TrustGate(OpenGate()), NoTracer()
    )
