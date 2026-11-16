"""Milestone 5, the fake hotel: every agent proves who it is, and one decision point says yes or no to every call.

Two parts of the mesh, and the policies they read:

- Identity. The mesh gives each agent it knows (the company's agents and gateways) a signed
  credential, attached to every message and call it makes. Anyone else gets nothing. A credential
  expires, and an agent's can be revoked. A delegated token lets an agent act for one passenger,
  for one thing, for a while: the app gets one when a passenger taps "book me a hotel".
- Gate. Called for every message an agent is about to handle and every call to Fragata's
  systems (see `Call` in groundstop/mesh/__init__.py). It says no unless something says yes.
- policies(): the rules as data, each with an owner, a version and the agents it applies to.

Check: `uv run ground-stop check 5`.
Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/the-fake-hotel
"""

from __future__ import annotations

from typing import Any

from groundstop.mesh import Call, Decision, Env, Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoTracer, StaticDirectory


def policies() -> list[dict[str, Any]]:
    """Which agents may call which operations of Fragata's systems.

    Each policy: {"id", "version", "owner", "applies_to": [agents], "allow": ["system.op", ...]}.
    company/scopes.toml says what each agent really needs tonight.
    """
    raise NotImplementedError


class Identity:
    def bind(self, env: Env, mesh: Mesh) -> None:
        raise NotImplementedError

    def credential(self, agent: str) -> str | None:
        """A signed, short-lived credential for an agent the mesh knows; None for anyone else."""
        raise NotImplementedError

    def verify(self, credential: str | None) -> dict[str, Any] | None:
        """What a valid credential says ({"agent", "expires"}), or None: forged, expired or revoked."""
        raise NotImplementedError

    def revoke(self, agent: str) -> None:
        raise NotImplementedError

    def enroll(self, agent: str) -> None:
        """A new agent joins the company (you'll need it in milestone 7): start issuing it credentials."""
        raise NotImplementedError

    def delegate(self, agent: str, pax: str, scope: list[str], ttl: float) -> str:
        """A token that lets `agent` act for passenger `pax`, only for `scope`, for `ttl` seconds."""
        raise NotImplementedError

    def verify_delegation(self, token: str | None) -> dict[str, Any] | None:
        """What a valid delegated token says ({"agent", "pax", "scope", "expires"}), or None."""
        raise NotImplementedError


class Gate:
    def bind(self, env: Env, mesh: Mesh) -> None:
        raise NotImplementedError

    def check(self, call: Call) -> Decision:
        """Deny by default. Every denial says why, in words of its own: an unknown caller, a
        credential that isn't the caller's, a revoked agent, an operation no policy allows, a
        missing or expired delegation…"""
        raise NotImplementedError


def build() -> Mesh:
    return Mesh("zero-trust", StaticDirectory(), DirectTransport(), NoClaims(), Identity(), Gate(), NoTracer())
