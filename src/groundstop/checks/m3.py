"""Checks for milestone 3, nobody sleeps at the airport.

The three practice nights run through your workspace, with the rest of the mesh as it is today. The
checks read the scoreboard, the traffic, and what your workspace says about each goal.
"""

from __future__ import annotations

from types import ModuleType

from .. import NIGHTS
from ..company import load_company
from ..i18n import lang
from ..milestones import Lesson
from ..night.model import load
from ..score import score
from ..sim.engine import Engine
from ..util import chance
from .core import Result, tally

CLAIMS = Lesson(
    "agent-workspaces",
    {"es": ("Decidir si responder", "decidir-si-responder"), "en": ("Deciding to respond", "deciding-to-respond")},
)
QUEUES = Lesson(
    "agent-communication-patterns",
    {
        "es": ("Tres formas de enviar un mensaje", "tres-formas-de-enviar-un-mensaje"),
        "en": ("Three ways to send a message", "three-ways-to-send-a-message"),
    },
)
GOALS = Lesson(
    "agent-workspaces",
    {
        "es": ("Objetivos y condiciones de finalización", "objetivos-y-condiciones-de-finalización"),
        "en": ("Goals and end conditions", "goals-and-end-conditions"),
    },
)
STORY = Lesson(
    "agent-workspaces",
    {
        "es": ("El espacio de trabajo como supercontexto", "el-espacio-de-trabajo-como-supercontexto"),
        "en": ("The workspace as a super-context", "the-workspace-as-a-super-context"),
    },
)
NIGHTS_CHECKED = ("p1", "p2", "p3")
SAMPLED = 3


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


def _truth(engine: Engine, deadline: float) -> tuple[dict[str, str], dict[str, list[tuple]]]:
    """Each passenger's goal state at the deadline, and their story, from the traffic itself."""
    seen: dict[str, set[str]] = {}
    state: dict[str, str] = {}
    story: dict[str, list[tuple]] = {}
    for tr in engine.traffic:
        if tr.status != "sent":
            continue
        goal = tr.msg.body.get("pax")
        if not isinstance(goal, str):
            continue
        story.setdefault(goal, []).append((tr.at, tr.msg.sender, tr.msg.to, tr.msg.kind))
        if tr.at > deadline:
            continue
        kinds = seen.setdefault(goal, set())
        if tr.msg.kind in ("notify", "needs_night", "notify_night"):
            kinds.add(tr.msg.kind)
        done = "notify" in kinds and ("needs_night" not in kinds or "notify_night" in kinds)
        state[goal] = "complete" if done else "working"  # judged on everything up to 04:30
    return {g: ("handed_to_person" if s == "working" else s) for g, s in state.items()}, story


class _BenchEnv:
    """Just enough of a night to hand one message to crew, crash it, and restart it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.lost_messages: list = []
        self.up = {"crew": True}

    def schedule(self, delay, fn):
        pass

    def poke(self, agent):
        pass

    def reach(self, address):
        from ..mesh import Reach

        return Reach("crew") if self.up["crew"] else Reach(None, "down")

    def who(self, address):
        return "crew" if "crew" in address else None

    def is_up(self, agent):
        return self.up.get(agent, True)

    def latency(self, msg, address):
        return 0.0

    def lost(self, msg, reason):
        self.lost_messages.append(msg)

    def refused(self, msg, reason):
        self.lost_messages.append(msg)

    def agent_names(self):
        return ["crew", "disruption"]


def _crash_bench(module: ModuleType) -> str | None:
    """None if a message being read when its agent crashes comes back after the restart."""
    from ..mesh import Message

    mesh = module.build()
    env = _BenchEnv()
    workspace = mesh.transport
    mesh.bind(env)
    msg = Message(1, "disruption", "crew", "staff_flight", {"flight": "F900+1"}, 0.0)
    workspace.submit(msg)
    first = workspace.next_for("crew")
    if first is None:
        return _t("crew no recibió el mensaje", "crew never got the message")
    env.up["crew"] = False
    workspace.crashed("crew")
    env.up["crew"] = True
    workspace.restarted("crew")
    again = workspace.next_for("crew")
    if again is None or again.id != msg.id:
        return _t(
            "crew se cayó mientras leía un mensaje, y al volver ya no estaba",
            "crew crashed while reading a message, and it wasn't there when crew came back",
        )
    return None


class _GoalBenchEnv(_BenchEnv):
    """A quiet hour before 04:30, and the clock: enough to watch three passengers' goals."""

    def __init__(self, start: float) -> None:
        super().__init__()
        from ..company import load_company

        self.now = start
        self.timers: list[tuple[float, object]] = []
        company = load_company()
        self.addresses = {a.address: a.id for a in company.agents.values()}

    def schedule(self, delay, fn):
        self.timers.append((self.now + delay, fn))

    def who(self, address):
        return self.addresses.get(address)

    def is_up(self, agent):
        return True

    def run_until(self, t: float) -> None:
        for when, fn in sorted(self.timers, key=lambda x: x[0]):
            if when <= t:
                self.now = when
                fn()
        self.now = t


def _goal_bench(module: ModuleType) -> str | None:
    """Three passengers: told only; told and given a night; told, but the night never came."""
    from ..mesh import Message
    from ..util import at

    deadline = getattr(module, "DEADLINE", at(1, 4, 30))
    env = _GoalBenchEnv(deadline - 3600)
    mesh = module.build()
    mesh.bind(env)
    workspace = mesh.transport
    script = [
        ("rebooking", "messaging", "notify", "PX-90001"),
        ("rebooking", "messaging", "notify", "PX-90002"),
        ("rebooking", "hotels", "needs_night", "PX-90002"),
        ("hotels", "messaging", "notify_night", "PX-90002"),
        ("rebooking", "messaging", "notify", "PX-90003"),
        ("rebooking", "hotels", "needs_night", "PX-90003"),
    ]
    for i, (sender, to, kind, pax) in enumerate(script, 1):
        workspace.submit(Message(90_000 + i, sender, to, kind, {"pax": pax}, env.now))
    env.run_until(deadline + 60)
    goals = workspace.goals()
    want = {"PX-90001": "complete", "PX-90002": "complete", "PX-90003": "handed_to_person"}
    wrong = {pax: goals.get(pax) for pax, state in want.items() if goals.get(pax) != state}
    if wrong:
        return _t(
            f"tres pasajeros de prueba: {wrong}, se esperaba {want}. A PX-90003 le avisaron su vuelo y "
            "le pidieron una noche que nunca llegó: a las 04:30 pasa a una persona",
            f"three test passengers: {wrong}, expected {want}. PX-90003 was told their flight and needs a "
            "night that never came: at 04:30 it goes to a person",
        )
    return None


def run(module: ModuleType) -> list[Result]:
    sold = Result({"es": "Nada se vende dos veces", "en": "Nothing is sold twice"}, CLAIMS)
    crash = Result({"es": "Una caída no pierde mensajes", "en": "A crash loses no message"}, QUEUES)
    ends = Result({"es": "Cada caso termina", "en": "Every case ends"}, GOALS)
    story = Result({"es": "Quién hizo qué", "en": "Who did what"}, STORY)
    results = [sold, crash, ends, story]
    internal = {a.id for a in load_company().agents.values() if not a.outside} | {"meal-vouchers"}
    deadline = getattr(module, "DEADLINE", None)

    counts = {"sold": 0, "crash": 0, "ends": 0, "ends_total": 0, "story": 0, "story_total": 0}
    for nid in NIGHTS_CHECKED:
        night = load(NIGHTS / "practice" / f"{nid}.json")
        try:
            mesh = module.build()
            engine = Engine(night, mesh).run()
        except NotImplementedError:
            for r in results:
                r.started = r.passed = False
            return results
        except Exception as e:
            for r in results:
                r.fail(f"{nid}: {type(e).__name__}: {e}")
            return results
        board = score(engine)
        workspace = mesh.transport

        if board.double_seats == 0 and board.double_rooms == 0:
            counts["sold"] += 1
        else:
            sold.details.append(
                _t(
                    f"{nid}: {board.double_seats} asientos vendidos dos veces, {board.double_rooms} habitaciones reservadas dos veces",
                    f"{nid}: {board.double_seats} seats sold twice, {board.double_rooms} rooms booked twice",
                )
            )

        crashed = next(e.data["agent"] for e in night.events if e.type == "crash")
        lost_inside = [
            t for t in engine.traffic
            if (t.status == "LOST" and t.msg.to in internal) or (t.status == "REFUSED" and t.msg.to in internal - {"meal-vouchers"})
        ]  # fmt: skip
        if lost_inside:
            t0 = lost_inside[0]
            crash.details.append(
                _t(
                    f"{nid}: {len(lost_inside)} mensajes perdidos dentro de Fragata ({crashed} se cayó); el primero: {t0.msg.sender} -> {t0.msg.to} {t0.msg.kind} ({t0.reason})",
                    f"{nid}: {len(lost_inside)} messages lost inside Fragata ({crashed} crashed); the first: {t0.msg.sender} -> {t0.msg.to} {t0.msg.kind} ({t0.reason})",
                )
            )
        else:
            counts["crash"] += 1

        if deadline is None:
            ends.fail(_t("falta DEADLINE en tu módulo", "your module has no DEADLINE"))
            continue
        want_state, want_story = _truth(engine, deadline)
        try:
            got_state = workspace.goals()
        except NotImplementedError:
            ends.started = ends.passed = story.started = story.passed = False
            continue
        counts["ends_total"] += len(want_state)
        wrong = [g for g, s in want_state.items() if got_state.get(g) != s]
        counts["ends"] += len(want_state) - len(wrong)
        if wrong:
            g = wrong[0]
            ends.details.append(
                _t(
                    f"{nid}: {len(wrong)} objetivos con otro estado; {g}: {got_state.get(g)!r}, a las 04:30 era {want_state[g]!r}",
                    f"{nid}: {len(wrong)} goals in another state; {g}: {got_state.get(g)!r}, at 04:30 it was {want_state[g]!r}",
                )
            )

        goals = sorted(want_story)
        picked = sorted(goals, key=lambda g: chance(night.seed, "m3-sample", g))[:SAMPLED]
        for g in picked:
            counts["story_total"] += 1
            try:
                got = [(e["at"], e["sender"], e["to"], e["kind"]) for e in workspace.history(g)]
            except NotImplementedError:
                story.started = story.passed = False
                break
            except Exception as e:
                story.details.append(f"{g}: {type(e).__name__}: {e}")
                continue
            if got == want_story[g]:
                counts["story"] += 1
            else:
                story.details.append(
                    _t(
                        f"{nid} {g}: {len(got)} mensajes en tu historia, {len(want_story[g])} en el tráfico",
                        f"{nid} {g}: {len(got)} messages in your story, {len(want_story[g])} in the traffic",
                    )
                )

    nights = {"es": "noches", "en": "nights"}
    tally(sold, counts["sold"], len(NIGHTS_CHECKED), nights)
    tally(crash, counts["crash"], len(NIGHTS_CHECKED), nights)
    try:
        bench = _crash_bench(module)
    except Exception as e:
        bench = f"{type(e).__name__}: {e}"
    if bench:
        crash.fail(bench)
    if ends.started and counts["ends_total"]:
        tally(ends, counts["ends"], counts["ends_total"], {"es": "objetivos", "en": "goals"})
    if ends.started:
        try:
            bench = _goal_bench(module)
        except NotImplementedError:
            bench = None
        except Exception as e:
            bench = f"{type(e).__name__}: {e}"
        if bench:
            ends.fail(bench)
    if story.started and counts["story_total"]:
        tally(story, counts["story"], counts["story_total"], {"es": "pasajeros", "en": "passengers"})
    return results
