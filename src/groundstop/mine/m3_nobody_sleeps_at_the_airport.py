"""Milestone 3, nobody sleeps at the airport: a workspace where messages wait, cases have one owner, and every case ends.

Your Workspace is two parts of the mesh at once (see groundstop/mesh/__init__.py):
- the transport: a message waits in the workspace until its agent has handled it, so an agent
  that crashes reads it when it's back;
- the claims: the first agent to claim a case or a seat has it; the others hear no.
It also keeps the goals: one per passenger, with its story and its state.

Check: `uv run ground-stop check 3`. See it in a night: put your Workspace in mine/mesh.py and run
`uv run ground-stop replay --mesh mine`.

Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/nobody-sleeps-at-the-airport
"""

from __future__ import annotations

from groundstop.mesh import Env, Mesh, Message
from groundstop.mesh.naive import NoIdentity, NoTracer, OpenGate, StaticDirectory
from groundstop.util import at

DEADLINE = at(1, 4, 30)  # 04:30: a case still open is handed to a person (the duty manager)


class Workspace:
    def bind(self, env: Env, mesh: Mesh) -> None:
        """Called once before the night. Keep env (the clock, the network) and mesh (its other parts)."""
        raise NotImplementedError

    # the transport

    def submit(self, msg: Message) -> None:
        """A sender hands over a message. To an agent inside Fragata: keep it until it's handled.
        To a partner outside: deliver it over the network (env.reach), trying again if nobody answers.
        If the directory has no address for it at all, refuse it (env.refused): there's nobody to keep it for."""
        raise NotImplementedError

    def next_for(self, agent: str) -> Message | None:
        """The agent is free: the next message it hasn't handled, or None."""
        raise NotImplementedError

    def ack(self, agent: str, msg: Message) -> None:
        """The agent finished handling msg: it can go."""
        raise NotImplementedError

    def crashed(self, agent: str) -> None:
        """The agent died. Whatever it was reading wasn't handled."""
        raise NotImplementedError

    def restarted(self, agent: str) -> None:
        raise NotImplementedError

    # the claims

    def claim(self, caller: str, key: str) -> bool:
        raise NotImplementedError

    def release(self, caller: str, key: str) -> None:
        raise NotImplementedError

    # the goals: one per passenger (a message is about a passenger when its body has "pax")

    def goals(self) -> dict[str, str]:
        """Every goal and its state: "working", "complete" or "handed_to_person"."""
        raise NotImplementedError

    def history(self, goal: str) -> list[dict]:
        """The goal's story: every message about that passenger, in order, as
        {"at": time, "sender": ..., "to": ..., "kind": ...}."""
        raise NotImplementedError


def build() -> Mesh:
    workspace = Workspace()
    return Mesh("workspace", StaticDirectory(), workspace, workspace, NoIdentity(), OpenGate(), NoTracer())
