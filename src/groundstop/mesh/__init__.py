"""The mesh: the parts every agent's messages and calls go through.

The agents are other teams' code and never change. They talk only through the SDK (`ctx.send`,
`ctx.publish`, `ctx.call`, `ctx.find`, `ctx.claim`), and the SDK hands every request to one of
these parts. Swap a part and the same agents behave differently. That is the project: each
milestone replaces one part of the naive mesh with your own.

| Part | Answers | Naive version | Milestone |
|---|---|---|---|
| directory | where is `crew`? who can check entry rules? | addresses hardcoded in each team's config | 4 |
| transport | get this message to `crew`, now or later | send it now; if nobody answers, it's gone | 3 |
| claims | is anyone already handling this passenger? | everyone thinks they're alone | 3 |
| identity | who is really calling? | whatever name the caller gives | 5 |
| gate | may this call go through? | everything goes through | 5, 6 |
| tracer | which request was this part of? | nothing is recorded | 4 |
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Message:
    id: int
    sender: str  # the name the sender says it has (nothing checks it in the naive mesh)
    to: str  # an agent name, or an address like https://…
    kind: str
    body: dict[str, Any]
    sent_at: float
    credential: str | None = None  # set by the identity part, if any
    trace: str | None = None  # set by the tracer, if any
    parent: int | None = None  # the message that caused this one
    local: bool = False  # work an agent queued for itself; never leaves the agent
    delegation: str | None = None  # a token that lets the sender act for one passenger (milestone 5)


@dataclass(frozen=True)
class Call:
    """One request the gate decides on: a message reaching an agent, or an agent calling a system."""

    kind: str  # "message" or "system"
    caller: str
    credential: str | None
    target: str  # agent name, or "system.op" like "vouchers.issue"
    action: str  # message kind, or the system operation
    body: dict[str, Any]
    at: float
    delegation: str | None = None  # the delegated token the message carried, if any
    sent_at: float | None = None  # when the message was handed to the mesh (a system call: now)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


ALLOW = Decision(True)


@dataclass(frozen=True)
class Reach:
    agent: str | None  # who answers at the address, if anyone
    reason: str = ""  # why nobody does


class Env(Protocol):
    """What the simulation lends the mesh parts."""

    @property
    def now(self) -> float: ...

    def schedule(self, delay: float, fn: Callable[[], None]) -> None: ...

    def poke(self, agent: str) -> None:
        """Tell the simulation an agent may have something to read."""

    def reach(self, address: str) -> Reach:
        """Who answers at an address right now (a network connection)."""

    def is_up(self, agent: str) -> bool: ...

    def latency(self, msg: Message, address: str) -> float: ...

    def lost(self, msg: Message, reason: str) -> None:
        """Record a message that should have arrived and never will."""

    def refused(self, msg: Message, reason: str) -> None:
        """Record a message the mesh decided not to deliver (to an agent it doesn't know, say)."""

    def who(self, address: str) -> str | None:
        """Which agent is registered at an address, whether it's up or not."""

    def agent_names(self) -> list[str]:
        """Every agent running tonight, inside Fragata or at a partner."""

    def version_of(self, agent: str) -> str:
        """The version of an agent that's running now."""

    def quarantine(self, agent: str, reason: str) -> None:
        """Pause an agent: it handles nothing until released; its messages wait (milestone 6)."""

    def release(self, agent: str) -> None: ...


class Directory(Protocol):
    def resolve(self, caller: str, name: str) -> str | None:
        """The address to reach `name` at, as `caller` knows it."""

    def find(self, caller: str, purpose: str) -> str | None:
        """The one agent whose purpose matches, or None."""

    def subscribers(self, caller: str, topic: str) -> list[str]:
        """Who should hear about an event `caller` publishes."""


class Transport(Protocol):
    def submit(self, msg: Message) -> None:
        """Take a message from its sender."""

    def next_for(self, agent: str) -> Message | None:
        """The next message for an agent that is free to read one."""

    def ack(self, agent: str, msg: Message) -> None:
        """The agent finished handling the message."""

    def crashed(self, agent: str) -> None: ...

    def restarted(self, agent: str) -> None: ...


class Claims(Protocol):
    def claim(self, caller: str, key: str) -> bool:
        """True if `caller` may work on `key` (a passenger case, a seat): nobody else has it."""

    def release(self, caller: str, key: str) -> None: ...


class Identity(Protocol):
    def credential(self, agent: str) -> str | None:
        """What an agent presents with every message and call."""


class Gate(Protocol):
    def check(self, call: Call) -> Decision: ...


class Tracer(Protocol):
    def stamp(self, msg: Message, parent: Message | None) -> None:
        """Give a new message its trace, from the message being handled (if any)."""


@dataclass
class Mesh:
    name: str
    directory: Directory
    transport: Transport
    claims: Claims
    identity: Identity
    gate: Gate
    tracer: Tracer
    extras: dict[str, Any] = field(default_factory=dict)

    def bind(self, env: Env) -> None:
        """Hand every part the simulation (and the mesh, to reach the other parts)."""
        seen: set[int] = set()
        for part in (self.directory, self.transport, self.claims, self.identity, self.gate, self.tracer):
            if part is None or id(part) in seen:
                continue  # one object can be two parts (milestone 3's workspace): bind it once
            seen.add(id(part))
            bind = getattr(part, "bind", None)
            if bind:
                bind(env, self)


def build(spec: str = "naive") -> Mesh:
    """`naive`, or a module path whose `build()` returns a Mesh (your own, for a milestone)."""
    if spec == "naive":
        from .naive import build as naive

        return naive()
    import importlib

    module = importlib.import_module(spec)
    return module.build()
