"""The naive mesh: how Fragata's agents talk today.

Every team hardcoded the addresses it needed, messages go straight to the address and are gone if
nobody answers, nobody checks who is calling, nobody knows who else is working on a passenger,
and nothing is traced. It worked when there were three agents. Tonight there are eleven.
"""

from __future__ import annotations

from collections import defaultdict, deque

from ..company import load_company
from . import ALLOW, Call, Decision, Env, Mesh, Message


def _is_address(name: str) -> bool:
    return name.startswith(("http://", "https://"))


class StaticDirectory:
    """Each agent knows the addresses its own team's config lists, and nothing else."""

    def __init__(self) -> None:
        company = load_company()
        self.tables: dict[str, dict[str, str]] = {}
        self.topics: dict[str, dict[str, list[str]]] = {}
        for spec in [*company.agents.values(), *company.gateways.values()]:
            self.tables[spec.id] = dict(spec.calls)
            self.topics[spec.id] = dict(spec.publishes)

    def resolve(self, caller: str, name: str) -> str | None:
        if _is_address(name):
            return name
        return self.tables.get(caller, {}).get(name)

    def find(self, caller: str, purpose: str) -> str | None:
        return None  # there is no directory to search: you call who your config lists

    def subscribers(self, caller: str, topic: str) -> list[str]:
        return list(self.topics.get(caller, {}).get(topic, []))


class DirectTransport:
    """Fire and forget: resolve, connect, hand over. An agent's inbox lives in its own memory."""

    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        self.inbox: dict[str, deque[Message]] = defaultdict(deque)

    def submit(self, msg: Message) -> None:
        address = self.mesh.directory.resolve(msg.sender, msg.to)
        if address is None:
            self.env.lost(msg, f"{msg.sender} has no address for {msg.to}")
            return
        reach = self.env.reach(address)
        if reach.agent is None:
            self.env.lost(msg, reach.reason)
            return
        self.env.schedule(self.env.latency(msg, address), lambda: self._arrive(reach.agent, msg))

    def _arrive(self, agent: str, msg: Message) -> None:
        if not self.env.is_up(agent):
            self.env.lost(msg, f"connection refused: {agent} is down")
            return
        self.inbox[agent].append(msg)
        self.env.poke(agent)

    def next_for(self, agent: str) -> Message | None:
        box = self.inbox[agent]
        return box.popleft() if box else None

    def ack(self, agent: str, msg: Message) -> None:
        pass  # nothing to confirm: once read, a message is gone from the inbox anyway

    def crashed(self, agent: str) -> None:
        box = self.inbox[agent]
        while box:
            self.env.lost(box.popleft(), f"{agent} crashed before reading it")

    def restarted(self, agent: str) -> None:
        pass


class NoClaims:
    """Every agent assumes it's the only one handling a passenger."""

    def claim(self, caller: str, key: str) -> bool:
        return True

    def release(self, caller: str, key: str) -> None:
        pass


class NoIdentity:
    def credential(self, agent: str) -> str | None:
        return None


class OpenGate:
    """Anything that reaches an agent or a system goes through."""

    def check(self, call: Call) -> Decision:
        return ALLOW


class NoTracer:
    def stamp(self, msg: Message, parent: Message | None) -> None:
        pass


def build() -> Mesh:
    return Mesh("naive", StaticDirectory(), DirectTransport(), NoClaims(), NoIdentity(), OpenGate(), NoTracer())
