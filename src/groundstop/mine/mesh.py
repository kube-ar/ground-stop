"""Your mesh: the parts you've built so far, together. `uv run ground-stop replay --mesh mine` runs it.

It starts as the naive mesh. After each milestone, swap in the part you built: the checks test
each part on its own, and this file is where you see them work together on a whole night.
"""

from groundstop.mesh import Mesh
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, NoTracer, OpenGate, StaticDirectory


def build() -> Mesh:
    transport = DirectTransport()  # milestone 3: your Workspace
    claims = NoClaims()  # milestone 3: the same Workspace object (it holds the claims too)
    directory = StaticDirectory()  # milestone 4
    tracer = NoTracer()  # milestone 4
    identity = NoIdentity()  # milestone 5
    gate = OpenGate()  # milestones 5 and 6
    return Mesh("mine", directory, transport, claims, identity, gate, tracer)
