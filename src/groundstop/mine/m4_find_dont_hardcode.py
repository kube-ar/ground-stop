"""Milestone 4, find, don't hardcode: a registry every agent is found through, and traces that follow a passenger.

Two parts of the mesh (see groundstop/mesh/__init__.py):

- Registry, the directory. Tonight each team publishes its agents and the platform reviewer
  approves them, before the first message; a partner publishes its new version when it moves;
  and an agent nobody invited publishes itself. Your registry decides what counts, and answers
  every `resolve` (where is X?) and every `find` (who does this?).
- Tracer. Every message gets a trace id; one passenger's journey is one trace. It also records
  when each message was handled, so you can say where a passenger's time went.

People and their roles: `load_company().people` (company/people.toml).
Check: `uv run ground-stop check 4`. Follow a passenger: `uv run ground-stop trace PX-48097 --mesh mine`.

Instructions: https://kube.ar/agentic-mesh/project/ground-stop/find-dont-hardcode (en español: https://kube.ar/es/agentic-mesh/project/ground-stop/find-dont-hardcode)
"""

from __future__ import annotations

from typing import Any

from groundstop.company import load_company
from groundstop.mesh import Env, Mesh, Message
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, OpenGate


class Registry:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        self.topics = {
            s.id: dict(s.publishes) for s in load_company().agents.values()
        }  # who hears which events (given)

    def subscribers(self, caller: str, topic: str) -> list[str]:
        return list(self.topics.get(caller, {}).get(topic, []))

    # the marketplace: every action is a person's, with a role

    def publish(self, entry: dict[str, Any], by: str) -> bool:
        """A person publishes an entry: id, version, owner, purpose, address, visibility, kind.
        It isn't active until a reviewer approves it."""
        raise NotImplementedError

    def approve(self, agent: str, version: str, by: str) -> bool:
        """A reviewer approves a published version. It becomes the active one; an older one is superseded."""
        raise NotImplementedError

    def retire(self, agent: str, by: str) -> bool:
        """The owner retires an agent: nobody can resolve or find it any more. Its entries are kept."""
        raise NotImplementedError

    def entries(self) -> list[dict[str, Any]]:
        """Every entry ever published, each with its status: pending, active, superseded or retired."""
        raise NotImplementedError

    def audit(self) -> list[dict[str, Any]]:
        """Every action, in order: {"at", "action", "agent", "version", "by", "role", "ok"}."""
        raise NotImplementedError

    # the directory

    def resolve(self, caller: str, name: str) -> str | None:
        """The address of the active version of `name`; None if there is none.
        A name that is already an address (http…) resolves to itself: someone gave it out."""
        raise NotImplementedError

    def find(self, caller: str, purpose: str) -> str | None:
        """Discovery: the one active agent, visible to the caller, whose purpose matches; or None."""
        raise NotImplementedError


class Tracer:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env = env

    def stamp(self, msg: Message, parent: Message | None) -> None:
        """Give a new message its trace id (set msg.trace) and remember it as a span.

        A message about a passenger (its body has "pax") belongs to that passenger's trace: the
        first message about them starts it. Any other message continues the trace of the message
        being handled (`parent`), if there is one. msg.parent is the id of the message that caused it.
        """
        raise NotImplementedError

    def handled(self, agent: str, msg: Message) -> None:
        """`agent` finished handling `msg`, now (env.now)."""
        raise NotImplementedError

    def trace_of(self, pax: str) -> str | None:
        raise NotImplementedError

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        """The trace's spans, one per message, in the order they were sent:
        {"id", "parent", "sender", "to", "kind", "sent_at", "handled_at"}."""
        raise NotImplementedError

    def slowest_hop(self, trace_id: str) -> dict[str, Any]:
        """Where the time went: {"agent", "seconds"} for the longest hop.

        A hop starts when a message is sent and ends when the agent that got it sends the next
        message of the trace it caused (or finishes handling it, if it sends none). The hop's time
        belongs to that receiving agent.
        """
        raise NotImplementedError


def build() -> Mesh:
    return Mesh("registry", Registry(), DirectTransport(), NoClaims(), NoIdentity(), OpenGate(), Tracer())
