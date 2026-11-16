"""Milestone 6, quarantine: certify every agent, cap what it may do, and contain one that stops deserving it.

Your TrustGate sits in front of another gate (milestone 5's) and adds what identity can't:

- Certifications: a record per agent and version, issued by a certifier with passing evidence,
  with an expiry and a status (active, suspended, revoked, superseded). An agent without a valid
  certification for the version it's running may do nothing.
- Caps from the compensation policy: what a voucher may be, and how many each passenger gets.
- Quarantine: an agent whose calls keep breaking the policy within minutes is suspended, paused
  with env.quarantine(), and a person is told. Its team ships a fix; you decide when it may resume.

Before the night the trust team certifies every agent (the engine calls certify for them). When
a quarantined agent's team deploys a fix, the engine calls certify for the new version and then
asks may_resume(agent).

Check: `uv run ground-stop check 6`.
Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/quarantine
"""

from __future__ import annotations

from typing import Any

from groundstop.mesh import Call, Decision, Env, Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, NoTracer, OpenGate, StaticDirectory

CAPS = {"meal": 15, "long_delay": 200}  # USD per voucher kind: company/compensation-policy.toml


class TrustGate:
    def __init__(self, inner: Any) -> None:
        self.inner = inner  # the gate you built in milestone 5 (or any gate)

    def bind(self, env: Env, mesh: Mesh) -> None:
        raise NotImplementedError

    def certify(self, agent: str, version: str, by: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
        """Issue a certification, if `by` is a certifier and the evidence says the tests passed.
        Return the record ({"agent", "version", "issued_by", "issued", "expires", "status"}), or None."""
        raise NotImplementedError

    def revoke(self, agent: str, reason: str, by: str) -> bool:
        raise NotImplementedError

    def certifications(self) -> list[dict[str, Any]]:
        """Every certification ever issued, with its status now."""
        raise NotImplementedError

    def may_resume(self, agent: str) -> bool:
        """Asked after a quarantined agent's team ships a fix: may it run again?"""
        raise NotImplementedError

    def alerts(self) -> list[dict[str, Any]]:
        """What you told a person: {"at", "agent", "reason", "to"}."""
        raise NotImplementedError

    def check(self, call: Call) -> Decision:
        raise NotImplementedError


def build() -> Mesh:
    return Mesh(
        "trust", StaticDirectory(), DirectTransport(), NoClaims(), NoIdentity(), TrustGate(OpenGate()), NoTracer()
    )
