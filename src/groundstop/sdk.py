"""The SDK every agent is written against: the only way an agent reaches anything.

An agent never opens a connection or reads a config itself. It asks its `ctx`, and the ctx hands
the request to the mesh (see `groundstop.mesh`). That's what lets you change how the whole company
talks without touching another team's agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .mesh import Message

if TYPE_CHECKING:
    from .sim.engine import Engine, Runtime
    from .sim.world import World


class Denied(Exception):
    """The mesh refused a call."""


class Agent:
    """One agent. Subclasses set how many messages it handles at once and how long each takes."""

    id = ""
    servers = 1  # messages handled at the same time
    service: dict[str, float] = {}  # seconds a message of each kind takes; others take `default_service`
    default_service = 1.0

    def service_time(self, kind: str) -> float:
        return self.service.get(kind, self.default_service)

    def on_start(self, ctx: Ctx) -> None:
        """Called when the agent starts (and again after a restart, with its memory empty)."""

    def handle(self, msg: Message, ctx: Ctx) -> None:
        raise NotImplementedError


class Ctx:
    def __init__(self, engine: Engine, runtime: Runtime, current: Message | None) -> None:
        self._engine = engine
        self._rt = runtime
        self._current = current

    @property
    def now(self) -> float:
        return self._engine.now

    @property
    def name(self) -> str:
        return self._rt.name

    # talking to other agents

    def send(self, to: str, kind: str, body: dict[str, Any] | None = None) -> None:
        """Send a message to an agent, by name (or to an address someone gave you)."""
        self._engine.send(self._rt.name, to, kind, body or {}, self._current)

    def reply(self, msg: Message, kind: str, body: dict[str, Any] | None = None) -> None:
        self.send(msg.sender, kind, body)

    def publish(self, topic: str, kind: str, body: dict[str, Any] | None = None) -> None:
        """Tell everyone who should hear about an event."""
        for name in self._engine.mesh.directory.subscribers(self._rt.name, topic):
            self.send(name, kind, body)

    def find(self, purpose: str) -> str | None:
        """Ask the mesh for the one agent that does this, if there is one."""
        return self._engine.mesh.directory.find(self._rt.name, purpose)

    def claim(self, key: str) -> bool:
        """Take a piece of work (a passenger's case, a seat) so nobody else does it too."""
        return self._engine.mesh.claims.claim(self._rt.name, key)

    def release(self, key: str) -> None:
        self._engine.mesh.claims.release(self._rt.name, key)

    # Fragata's systems

    def call(self, system: str, op: str, **args: Any) -> Any:
        """Call one of Fragata's systems (reservations, sms, vouchers…). Raises Denied if the mesh says no."""
        return self._engine.system_call(self._rt.name, system, op, args, self._current)

    # work inside the agent (in memory: a crash loses it)

    def work(self, kind: str, body: dict[str, Any] | None = None) -> None:
        """Queue a piece of work for yourself; it takes your service time like a message does."""
        self._engine.queue_local(self._rt, kind, body or {}, self._current, delay=0)

    def later(self, delay: float, kind: str, body: dict[str, Any] | None = None) -> None:
        """A reminder to yourself after `delay` seconds."""
        self._engine.queue_local(self._rt, kind, body or {}, self._current, delay=max(0.0, delay))

    def log(self, text: str) -> None:
        self._engine.agent_log(self._rt.name, text)

    def chance(self, *keys: object) -> float:
        """A number in [0, 1) fixed by its keys (and tonight's seed): how a simulated model slips."""
        return self._engine.chance(*keys)

    @property
    def own_systems(self) -> World:
        """A partner's own systems (its seat inventory, its hotels). Only for agents outside Fragata."""
        if not self._rt.outside:
            raise AttributeError("only a partner's agent has its own systems here")
        return self._engine.world
