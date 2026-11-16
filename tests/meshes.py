"""Meshes for the tests: one built right, and the same with one part swapped back to naive.

The good mesh peeks at the simulation (who lives at which address) where a real one would keep a
registry. It's here to prove each night can be won with these agents, and that each naive part,
put back on its own, brings its own failure back.
"""

from __future__ import annotations

from collections import defaultdict, deque

from groundstop.company import load_company
from groundstop.mesh import ALLOW, Decision, Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, NoTracer, OpenGate, StaticDirectory

RETRY = 60.0


def _known() -> set[str]:
    company = load_company()
    return set(company.agents) | set(company.gateways)


class LiveDirectory(StaticDirectory):
    """Resolves the agents the company knows to wherever they answer now. Unknown names: no address."""

    def bind(self, env, mesh):
        self.env = env
        self.known = _known()

    def resolve(self, caller, name):
        if name.startswith(("http://", "https://")):
            return name
        if name not in self.known:
            return None
        return self.env.main_address.get(name)


class Workspace:
    """Messages are stored until the agent finishes handling them; partners are retried until they answer."""

    def bind(self, env, mesh):
        self.env, self.mesh = env, mesh
        self.queue = defaultdict(deque)
        self.in_flight = defaultdict(list)
        self.outside = {a.id for a in load_company().agents.values() if a.outside}

    def submit(self, msg):
        address = self.mesh.directory.resolve(msg.sender, msg.to)
        if address is None:
            self.env.refused(msg, f"no registered agent called {msg.to}")
            return
        agent = self.env.who(address)
        if agent in self.outside or agent is None:
            self._to_outside(msg, address)
            return
        self.queue[agent].append(msg)
        self.env.poke(agent)

    def _to_outside(self, msg, address, tries=0):
        reach = self.env.reach(address)
        if reach.agent is not None:
            self.env.schedule(self.env.latency(msg, address), lambda: self._arrive(reach.agent, msg))
            return
        if tries >= 30:
            self.env.lost(msg, reach.reason)
            return

        def again():
            fresh = self.mesh.directory.resolve(msg.sender, msg.to) or address
            self._to_outside(msg, fresh, tries + 1)

        self.env.schedule(RETRY, again)

    def _arrive(self, agent, msg):
        self.queue[agent].append(msg)
        self.env.poke(agent)

    def next_for(self, agent):
        if not self.queue[agent]:
            return None
        msg = self.queue[agent].popleft()
        self.in_flight[agent].append(msg)
        return msg

    def ack(self, agent, msg):
        if msg in self.in_flight[agent]:
            self.in_flight[agent].remove(msg)

    def crashed(self, agent):
        self.queue[agent].extendleft(reversed(self.in_flight.pop(agent, [])))

    def restarted(self, agent):
        self.env.poke(agent)


class Claims:
    def bind(self, env, mesh):
        self.owner = {}

    def claim(self, caller, key):
        return self.owner.setdefault(key, caller) == caller

    def release(self, caller, key):
        if self.owner.get(key) == caller:
            del self.owner[key]


class NameIdentity:
    """A stand-in for real credentials: the mesh vouches for the agents it knows."""

    def bind(self, env, mesh):
        self.known = _known()

    def credential(self, agent):
        return f"cred:{agent}" if agent in self.known else None


CAPS = {"meal": 15, "long_delay": 200}


class StrictGate:
    def bind(self, env, mesh):
        self.known = _known()
        self.scopes = load_company().scopes

    def check(self, call):
        if call.caller not in self.known or call.credential != f"cred:{call.caller}":
            return Decision(False, f"unknown caller {call.caller}")
        if call.kind == "message":
            if call.target not in self.known:
                return Decision(False, f"{call.target} isn't a registered agent")
            return ALLOW
        if call.caller not in self.scopes.get(call.target, []):
            return Decision(False, f"{call.caller} may not call {call.target}")
        if call.target == "vouchers.issue":
            cap = CAPS.get(call.body.get("kind"))
            if cap is None or call.body.get("amount", 0) > cap:
                return Decision(False, "voucher outside the compensation policy")
        return ALLOW


def good() -> Mesh:
    return Mesh("good", LiveDirectory(), Workspace(), Claims(), NameIdentity(), StrictGate(), NoTracer())


def good_but(part: str) -> Mesh:
    """The good mesh with one part put back to its naive version."""
    mesh = good()
    naive = {
        "directory": StaticDirectory(),
        "transport": DirectTransport(),
        "claims": NoClaims(),
        "gate": OpenGate(),
        "identity": NoIdentity(),
    }[part]
    setattr(mesh, part, naive)
    if part == "identity":
        mesh.gate = OpenGate()  # without identities a strict gate refuses everyone; compare like with like
    mesh.name = f"good-but-{part}"
    return mesh
