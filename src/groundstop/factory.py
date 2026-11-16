"""The platform's kit for building agents (milestone 7): written once, used by every team.

- `try_agent(cls, kind, body)`: hand one message to an agent in a sandbox with p1's passengers,
  and see what it sends back and which systems it calls. For tests.
- `benchmark(new_agent, nights)`: replay nights with the reference mesh, with and without a new
  agent, and compare the scoreboards. For the pipeline's benchmark gate.
- `calls_in(cls)`: the systems an agent's code calls (`ctx.call("system", "op", …)`), read from
  its source and the functions it holds (a template's decide, say). For the pipeline's security scan.
"""

from __future__ import annotations

import inspect
import re
from typing import Any

from . import NIGHTS
from .mesh import Message
from .night.model import load

_CALL = re.compile(r"""ctx\.call\(\s*["']([a-z_-]+)["']\s*,\s*["']([a-z_]+)["']""")


def calls_in(cls: type) -> set[str]:
    """Every `system.op` the class's code calls, from its source (and its parents' up to Agent)."""
    found = set()
    for klass in inspect.getmro(cls):
        if klass.__module__.startswith("groundstop.sdk") or klass is object:
            continue
        pieces = [klass] + [
            v.__func__ if isinstance(v, staticmethod | classmethod) else v for v in vars(klass).values()
        ]
        for piece in pieces:
            if not (inspect.isclass(piece) or inspect.isfunction(piece)):
                continue
            try:
                source = inspect.getsource(piece)
            except (OSError, TypeError):
                continue
            found.update(f"{s}.{op}" for s, op in _CALL.findall(source))
    return found


class _SandboxCtx:
    """Just enough of a ctx for one message: the reservation system's passenger lookups, and a
    record of what the agent sends and calls."""

    def __init__(self, night, current: Message) -> None:
        self._night, self._current = night, current
        self.sent: list[tuple[str, str, dict]] = []
        self.calls: list[tuple[str, str, dict]] = []
        self.now = float(night.storm_start + 3600)
        self.name = current.to

    def send(self, to: str, kind: str, body: dict | None = None) -> None:
        self.sent.append((to, kind, dict(body or {})))

    def reply(self, msg: Message, kind: str, body: dict | None = None) -> None:
        self.send(msg.sender, kind, body)

    def call(self, system: str, op: str, **args: Any) -> Any:
        self.calls.append((system, op, dict(args)))
        if (system, op) == ("reservations", "passenger"):
            p = self._night.passenger(args["pax"])
            return {
                "id": p.id, "name": p.name, "lang": p.lang, "dest": p.dest, "flight": p.flight, "tier": p.tier,
                "local": p.local, "bags": p.bags, "interline": p.interline, "passport_group": p.passport_group, "visa": p.visa,
            }  # fmt: skip
        raise RuntimeError(f"the sandbox has no {system}.{op}")

    def log(self, text: str) -> None:
        pass

    def find(self, purpose: str) -> None:
        return None

    def claim(self, key: str) -> bool:
        return True


def try_agent(cls: type, kind: str, body: dict, sender: str = "hotels") -> dict[str, Any]:
    """Hand one message to a fresh instance of `cls`. Returns what it sent and which systems it called."""
    night = load(NIGHTS / "practice" / "p1.json")
    msg = Message(1, sender, "under-test", kind, dict(body), float(night.storm_start))
    ctx = _SandboxCtx(night, msg)
    agent = cls()
    agent.handle(msg, ctx)
    return {"sent": ctx.sent, "calls": ctx.calls}


def benchmark(new_agent: dict | None, nights: tuple[str, ...] = ("p1", "p2")) -> dict[str, dict]:
    """Scoreboards of practice nights with the reference mesh (milestones 3 to 6), without and with a new agent."""
    from .checks.core import reference
    from .mesh import Mesh
    from .score import score
    from .sim.engine import Engine

    m3, m4, m5, m6 = (reference(n) for n in "3456")
    out = {}
    for nid in nights:
        night = load(NIGHTS / "practice" / f"{nid}.json")
        boards = {}
        for label, extra in (("without", []), ("with", [new_agent] if new_agent else [])):
            workspace = m3.Workspace()
            mesh = Mesh(
                "benchmark", m4.Registry(), workspace, workspace, m5.Identity(), m6.TrustGate(m5.Gate()), m4.Tracer()
            )
            boards[label] = score(Engine(night, mesh, new_agents=extra).run()).to_json()
        out[nid] = boards
    return out
