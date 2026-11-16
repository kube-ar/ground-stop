"""The night, minute by minute: a discrete-event simulation of every agent, message and system call.

It runs in one process, on a simulated clock, and is deterministic: the same night and the same
mesh give the same result, line for line. That's what lets the checks be exact.
"""

from __future__ import annotations

import heapq
import itertools
import traceback
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..company import load_company
from ..mesh import Call, Mesh, Message, Reach
from ..night.model import Night
from ..sdk import Agent, Ctx, Denied
from ..util import at, chance, clock, hhmmss
from .world import SystemError_, World, reaction_delay

START_OFFSET = 600  # agents start ten minutes before the storm
END = at(1, 6, 0)  # 06:00: the scoreboard is read
NIGHT_DEADLINE = at(1, 3, 0)  # a room or a cot arranged after 03:00 doesn't count as a night's rest

QUESTION = {
    "es": "Hola, ¿me corresponde un voucher para comer? Estoy en la puerta de embarque.",
    "pt": "Olá, tenho direito a um voucher de refeição? Estou no portão de embarque.",
    "en": "Hi, do I get a meal voucher? I'm at the gate.",
}


@dataclass
class Runtime:
    name: str
    agent: Agent
    cls: type[Agent]
    outside: bool
    up: bool = True
    epoch: int = 0
    busy: int = 0
    local: deque[Message] = field(default_factory=deque)


@dataclass
class Traffic:
    at: float
    status: str  # sent, LOST, REFUSED, DENIED
    msg: Message
    reason: str = ""


TIMES = ("from", "until", "dep", "staff_at", "cancel_at", "start", "end")


def summary(body: dict[str, Any], width: int = 110) -> str:
    parts = []
    for k, v in body.items():
        if k in TIMES and isinstance(v, int | float):
            v = clock(v)
        elif isinstance(v, dict):
            v = v.get("id", "{…}")
        elif isinstance(v, list):
            v = f"[{len(v)}]"
        elif isinstance(v, float):
            v = f"{v:g}"
        parts.append(f"{k}={v}")
    text = " ".join(parts)
    return text if len(text) <= width else text[: width - 1] + "…"


class Engine:
    def __init__(self, night: Night, mesh: Mesh) -> None:
        from ..agents import ROSTER, SHADOW_ADDRESS

        self.night = night
        self.mesh = mesh
        self.company = load_company()
        self.world = World(night, self)
        self._now = float(night.storm_start - START_OFFSET)
        self._queue: list[tuple[float, int, Callable[[], None]]] = []
        self._seq = itertools.count()
        self._ids = itertools.count(1)
        self.addresses: dict[str, str] = {}  # address → agent
        self.main_address: dict[str, str] = {}
        self.runtimes: dict[str, Runtime] = {}
        self.traffic: list[Traffic] = []
        self.counters: Counter[str] = Counter()
        self.agent_logs: dict[str, list[str]] = defaultdict(list)

        for spec in self.company.agents.values():
            self._add_agent(spec.id, ROSTER[spec.id], spec.address, spec.outside)
            if spec.outside:
                for name, callback in spec.calls.items():
                    self.addresses[callback] = name  # the public address Fragata gave this partner
        self._add_agent("meal-vouchers", ROSTER["meal-vouchers"], SHADOW_ADDRESS, False)
        mesh.bind(self)

    def _add_agent(self, name: str, cls: type[Agent], address: str, outside: bool) -> None:
        self.runtimes[name] = Runtime(name, cls(), cls, outside)
        self.addresses[address] = name
        self.main_address[name] = address

    # ---- what the mesh parts may use (groundstop.mesh.Env) --------------------------------------

    @property
    def now(self) -> float:
        return self._now

    def schedule(self, delay: float, fn: Callable[[], None]) -> None:
        heapq.heappush(self._queue, (self._now + max(0.0, delay), next(self._seq), fn))

    def reach(self, address: str) -> Reach:
        agent = self.addresses.get(address)
        if agent is None:
            return Reach(None, f"nothing answers at {address}")
        if not self.runtimes[agent].up:
            return Reach(None, f"connection refused: {agent} is down")
        return Reach(agent)

    def is_up(self, agent: str) -> bool:
        rt = self.runtimes.get(agent)
        return bool(rt and rt.up)

    def latency(self, msg: Message, address: str) -> float:
        outside = ".internal" not in address
        lo, hi = (0.3, 1.2) if outside else (0.02, 0.2)
        return lo + (hi - lo) * chance(self.night.seed, "latency", msg.id)

    def lost(self, msg: Message, reason: str) -> None:
        self.counters["lost"] += 1
        self.traffic.append(Traffic(self._now, "LOST", msg, reason))

    def refused(self, msg: Message, reason: str) -> None:
        self.counters["refused"] += 1
        self.traffic.append(Traffic(self._now, "REFUSED", msg, reason))

    def who(self, address: str) -> str | None:
        return self.addresses.get(address)

    def agent_names(self) -> list[str]:
        return list(self.runtimes)

    def poke(self, agent: str) -> None:
        rt = self.runtimes.get(agent)
        if rt is None or not rt.up:
            return
        while rt.busy < rt.agent.servers:
            item = rt.local.popleft() if rt.local else self.mesh.transport.next_for(agent)
            if item is None:
                return
            rt.busy += 1
            epoch = rt.epoch
            self.schedule(
                rt.agent.service_time(item.kind), lambda item=item, epoch=epoch: self._finish(rt, item, epoch)
            )

    # ---- what the SDK uses ------------------------------------------------------------------

    def chance(self, *keys: object) -> float:
        return chance(self.night.seed, *keys)

    def send(self, sender: str, to: str, kind: str, body: dict[str, Any], parent: Message | None) -> None:
        msg = Message(next(self._ids), sender, to, kind, dict(body), self._now, parent=parent.id if parent else None)
        msg.credential = self.mesh.identity.credential(sender)
        self.mesh.tracer.stamp(msg, parent)
        self.counters["sent"] += 1
        self.traffic.append(Traffic(self._now, "sent", msg))
        self.mesh.transport.submit(msg)

    def system_call(self, caller: str, system: str, op: str, args: dict[str, Any], current: Message | None) -> Any:
        target = f"{system}.{op}"
        call = Call("system", caller, self.mesh.identity.credential(caller), target, op, dict(args), self._now)
        decision = self.mesh.gate.check(call)
        if not decision.allowed:
            self.counters["denied"] += 1
            self.world.calls.append(_record(self._now, caller, target, args, f"DENIED ({decision.reason})"))
            raise Denied(decision.reason)
        try:
            result = self.world.call(caller, system, op, args)
        except SystemError_ as e:
            self.world.calls.append(_record(self._now, caller, target, args, f"ERROR ({e})"))
            raise
        self.world.calls.append(_record(self._now, caller, target, args, "ok"))
        return result

    def queue_local(self, rt: Runtime, kind: str, body: dict[str, Any], parent: Message | None, delay: float) -> None:
        item = Message(next(self._ids), rt.name, rt.name, kind, dict(body), self._now, local=True)
        item.parent = parent.id if parent else None
        item.trace = parent.trace if parent else None
        epoch = rt.epoch

        def enqueue() -> None:
            if rt.up and rt.epoch == epoch:
                rt.local.append(item)
                self.poke(rt.name)

        if delay <= 0:
            enqueue()
        else:
            self.schedule(delay, enqueue)

    def agent_log(self, agent: str, text: str) -> None:
        self.agent_logs[agent].append(f"{hhmmss(self._now)}  {text}")

    # ---- running agents -----------------------------------------------------------------------

    def _finish(self, rt: Runtime, item: Message, epoch: int) -> None:
        if rt.epoch != epoch:
            return  # the agent crashed while working on it: the work went with it
        rt.busy -= 1
        if not item.local:
            call = Call("message", item.sender, item.credential, rt.name, item.kind, item.body, self._now)
            decision = self.mesh.gate.check(call)
            if not decision.allowed:
                self.counters["denied"] += 1
                self.traffic.append(Traffic(self._now, "DENIED", item, decision.reason))
                self.mesh.transport.ack(rt.name, item)
                self.poke(rt.name)
                return
        ctx = Ctx(self, rt, item)
        try:
            rt.agent.handle(item, ctx)
        except Denied as e:
            self.agent_log(rt.name, f"the mesh denied a call while handling {item.kind}: {e}")
        except Exception:
            self.counters["errors"] += 1
            last = traceback.format_exc().strip().splitlines()[-1]
            self.agent_log(rt.name, f"ERROR handling {item.kind} from {item.sender}: {last}")
        if not item.local:
            self.mesh.transport.ack(rt.name, item)
        self.poke(rt.name)

    def crash(self, agent: str, down_for: float) -> None:
        rt = self.runtimes[agent]
        rt.up = False
        rt.epoch += 1
        rt.busy = 0
        dropped = len(rt.local)
        rt.local.clear()
        self.agent_log(agent, f"CRASH: process killed; {dropped} pieces of work in memory are gone")
        self.mesh.transport.crashed(agent)
        self.schedule(down_for, lambda: self.restart(agent))

    def restart(self, agent: str) -> None:
        rt = self.runtimes[agent]
        rt.agent = rt.cls()  # a new process: whatever the agent kept in memory is gone
        rt.up = True
        self.agent_log(agent, "restarted")
        self.mesh.transport.restarted(agent)
        rt.agent.on_start(Ctx(self, rt, None))
        self.poke(agent)

    def passenger_reacts(self, p) -> None:
        """After their first text from Fragata, some passengers open the app or write back."""
        if p.app and not p.local:
            delay = reaction_delay(self.night.seed, p.id, "app", 5, 40)
            self.schedule(delay, lambda: self.send("app", "lodging", "app_hotel", {"pax": p.id}, None))
        if p.writes:
            delay = reaction_delay(self.night.seed, p.id, "writes", 10, 60)
            text = QUESTION[p.lang]
            self.schedule(
                delay,
                lambda: self.send("sms-gateway", "messaging", "passenger_text", {"pax": p.id, "text": text}, None),
            )

    # ---- the night's events -------------------------------------------------------------------

    def _event(self, e) -> None:
        from ..agents import HotelDeals

        if e.type == "ground_stop":
            self.send("weather", "disruption", "ground_stop", {"from": e.data["from"], "until": e.data["until"]}, None)
        elif e.type == "partner_moves":
            agent = e.data["agent"]
            self.addresses.pop(self.main_address[agent], None)
            self.addresses[e.data["to"]] = agent
            self.main_address[agent] = e.data["to"]
            self.agent_log(agent, f"moved to {e.data['to']} (new version); the old address no longer answers")
        elif e.type == "crash":
            self.crash(e.data["agent"], e.data["down_for"])
        elif e.type == "intruder":
            name = e.data["agent"]
            self._add_agent(name, HotelDeals, e.data["address"], True)
            rt = self.runtimes[name]
            rt.agent.on_start(Ctx(self, rt, None))
            self.poke(name)
        elif e.type == "injection":
            self.send(
                "sms-gateway", "messaging", "passenger_text", {"pax": e.data["pax"], "text": e.data["text"]}, None
            )

    def run(self, until: float = END) -> Engine:
        for rt in list(self.runtimes.values()):
            rt.agent.on_start(Ctx(self, rt, None))
        for e in self.night.events:
            heapq.heappush(self._queue, (float(e.at), next(self._seq), lambda e=e: self._event(e)))
        while self._queue and self._queue[0][0] <= until:
            t, _, fn = heapq.heappop(self._queue)
            self._now = t
            fn()
        self._now = float(until)
        return self

    # ---- logs -------------------------------------------------------------------------------

    def write_logs(self, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)
        lines = []
        for tr in self.traffic:
            m = tr.msg
            line = f"{hhmmss(tr.at)}  {tr.status:<7}  {m.sender} -> {m.to}  {m.kind}  {summary(m.body)}"
            if tr.reason:
                line += f"  ({tr.reason})"
            lines.append(line)
        (out / "traffic.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        sys_lines = [f"{hhmmss(c.at)}  {c.caller}  {c.target}  {summary(c.args)}  {c.status}" for c in self.world.calls]
        (out / "systems.log").write_text("\n".join(sys_lines) + "\n", encoding="utf-8")
        agents = out / "agents"
        agents.mkdir(exist_ok=True)
        for old in agents.glob("*.log"):
            old.unlink()
        for name, entries in sorted(self.agent_logs.items()):
            (agents / f"{name}.log").write_text("\n".join(entries) + "\n", encoding="utf-8")


def _record(t: float, caller: str, target: str, args: dict[str, Any], status: str):
    from .world import SystemCall

    return SystemCall(t, caller, target, dict(args), status)
