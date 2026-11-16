"""Milestone 3, reference (fast path): queues, claims and goals in plain Python, alive as long as the mesh is."""

from __future__ import annotations

from collections import defaultdict, deque

from groundstop.company import load_company
from groundstop.mesh import Env, Mesh, Message
from groundstop.mesh.naive import NoIdentity, NoTracer, OpenGate, StaticDirectory
from groundstop.util import at

DEADLINE = at(1, 4, 30)
RETRY = 60.0
TRIES = 30


class Workspace:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        self.queue: dict[str, deque[Message]] = defaultdict(deque)
        self.reading: dict[str, list[Message]] = defaultdict(list)
        self.owner: dict[str, str] = {}
        self.stories: dict[str, list[dict]] = defaultdict(list)
        self.state: dict[str, str] = {}
        self.needs: dict[str, set[str]] = defaultdict(set)
        self.outside = {a.id for a in load_company().agents.values() if a.outside}
        env.schedule(DEADLINE - env.now, self._hand_over)

    # the transport

    def submit(self, msg: Message) -> None:
        self._remember(msg)
        address = self.mesh.directory.resolve(msg.sender, msg.to)
        if address is None:  # the directory knows no such agent: the mesh won't deliver it
            self.env.refused(msg, f"no address for {msg.to}")
            return
        agent = self.env.who(address)
        if agent is None or agent in self.outside:
            self._deliver_outside(msg, address, 0)
            return
        self.queue[agent].append(msg)
        self.env.poke(agent)

    def _deliver_outside(self, msg: Message, address: str, tries: int) -> None:
        reach = self.env.reach(address)
        if reach.agent is not None:
            self.env.schedule(self.env.latency(msg, address), lambda: self._arrive(reach.agent, msg))
        elif tries >= TRIES:
            self.env.lost(msg, reach.reason)
        else:
            self.env.schedule(
                RETRY,
                lambda: self._deliver_outside(
                    msg, self.mesh.directory.resolve(msg.sender, msg.to) or address, tries + 1
                ),
            )

    def _arrive(self, agent: str, msg: Message) -> None:
        self.queue[agent].append(msg)
        self.env.poke(agent)

    def next_for(self, agent: str) -> Message | None:
        if not self.queue[agent]:
            return None
        msg = self.queue[agent].popleft()
        self.reading[agent].append(msg)
        return msg

    def ack(self, agent: str, msg: Message) -> None:
        if msg in self.reading[agent]:
            self.reading[agent].remove(msg)

    def crashed(self, agent: str) -> None:
        self.queue[agent].extendleft(reversed(self.reading.pop(agent, [])))

    def restarted(self, agent: str) -> None:
        self.env.poke(agent)

    # the claims

    def claim(self, caller: str, key: str) -> bool:
        return self.owner.setdefault(key, caller) == caller

    def release(self, caller: str, key: str) -> None:
        if self.owner.get(key) == caller:
            del self.owner[key]

    # the goals

    def _remember(self, msg: Message) -> None:
        goal = msg.body.get("pax")
        if not isinstance(goal, str):
            return
        self.stories[goal].append({"at": self.env.now, "sender": msg.sender, "to": msg.to, "kind": msg.kind})
        if self.state.get(goal) == "handed_to_person" or (self.is_closed and goal in self.state):
            return  # after 04:30 every goal has its final state: complete, or with a person
        if msg.kind in ("notify", "needs_night", "notify_night"):
            self.needs[goal].add(msg.kind)
        seen = self.needs[goal]
        done = "notify" in seen and ("needs_night" not in seen or "notify_night" in seen)
        self.state[goal] = "complete" if done else "working"  # a new need can reopen a goal

    def _hand_over(self) -> None:
        for goal, state in self.state.items():
            if state == "working":
                self.state[goal] = "handed_to_person"
        self.closed = True

    @property
    def is_closed(self) -> bool:
        return getattr(self, "closed", False)

    def goals(self) -> dict[str, str]:
        return dict(self.state)

    def history(self, goal: str) -> list[dict]:
        return list(self.stories.get(goal, []))


def build() -> Mesh:
    workspace = Workspace()
    return Mesh("workspace", StaticDirectory(), workspace, workspace, NoIdentity(), OpenGate(), NoTracer())
