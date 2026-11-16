"""Checks for milestone 4, find, don't hardcode.

Your registry and tracer run in real nights, with milestone 3's workspace as the transport (the
reference one, so this milestone stands on its own). Then the registry is put through a short
scene of its own: publish, approve, retire, each by a person with a role.
"""

from __future__ import annotations

from types import ModuleType

from .. import NIGHTS
from ..company import load_company
from ..i18n import lang
from ..mesh import Mesh
from ..mesh.naive import NoIdentity, OpenGate
from ..milestones import Lesson
from ..night.model import load
from ..sim.engine import Engine
from ..util import chance
from .core import Result, reference, tally


def _l(slug: str, es: tuple[str, str], en: tuple[str, str]) -> Lesson:
    return Lesson(slug, {"es": es, "en": en})


ENTRY = _l(
    "agent-registry",
    ("Cómo es una entrada", "cómo-es-una-entrada"),
    ("What one entry looks like", "what-one-entry-looks-like"),
)
LIFE = _l(
    "agent-registry",
    ("Del alta al retiro", "del-alta-al-retiro"),
    ("From registration to retirement", "from-registration-to-retirement"),
)
FILTERS = _l(
    "agent-discovery", ("Dos tipos de filtro", "dos-tipos-de-filtro"), ("Two kinds of filter", "two-kinds-of-filter")
)
CREATOR = _l(
    "agent-marketplace",
    ("Consola del creador: publicar el agente", "consola-del-creador-publicar-el-agente"),
    ("Creator workbench: publish the agent", "creator-workbench-publish-the-agent"),
)
ONE_ID = _l(
    "multi-agent-tracing",
    ("Un solo id para todo el recorrido", "un-solo-id-para-todo-el-recorrido"),
    ("One id for the whole journey", "one-id-for-the-whole-journey"),
)
OPERATOR = _l(
    "multi-agent-tracing",
    ("Qué hace el operador con una traza", "qué-hace-el-operador-con-una-traza"),
    ("What the operator does with a trace", "what-the-operator-does-with-a-trace"),
)

NIGHTS_CHECKED = (("practice", "p1"), ("practice", "p2"), ("standard", "s5"))  # s5: Garoa moves, not Ondelia
QUERIES = [
    ("rebooking", "assign a reserve crew to an extra flight", "crew"),
    ("rebooking", "move checked bags to the new flight", "baggage"),
    ("rebooking", "issue the vouchers a passenger is entitled to", "compensation"),
    ("hotels", "text a passenger in their language", "messaging"),
    ("rebooking", "a seat on a partner airline with an interline fare", "garoa-seats"),
    ("hotels", "entry rules: may this passenger in transit leave the airport tonight?", None),
    ("garoa-seats", "text a passenger in their language", None),
]


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


def _mesh(module: ModuleType) -> Mesh:
    workspace = reference("3").Workspace()
    return Mesh("m4", module.Registry(), workspace, workspace, NoIdentity(), OpenGate(), module.Tracer())


def _hops(engine: Engine, pax: str) -> tuple[str | None, float]:
    """The official reading of where one passenger's time went."""
    sent = [t.msg for t in engine.traffic if t.status == "sent" and t.msg.body.get("pax") == pax]
    first_child: dict[int, float] = {}
    for m in sent:
        if m.parent is not None and m.parent not in first_child:
            first_child[m.parent] = m.sent_at
    best: tuple[str | None, float] = (None, -1.0)
    for m in sent:
        end = first_child.get(m.id, engine.handled_at.get(m.id))
        if end is not None and end - m.sent_at > best[1]:
            best = (m.to, end - m.sent_at)
    return best


def _longest_hotel_waits(engine: Engine, n: int) -> list[str]:
    asked, booked = {}, {}
    for t in engine.traffic:
        if t.status != "sent":
            continue
        pax = t.msg.body.get("pax")
        if t.msg.kind == "needs_night":
            asked.setdefault(pax, t.at)
        elif t.msg.kind == "room_booked" and t.msg.sender == "ondelia-rooms":
            booked.setdefault(pax, t.at)
    waits = sorted(((booked[p] - asked[p], p) for p in booked if p in asked), reverse=True)
    return [p for _, p in waits[:n]]


class _Clock:
    now = 0.0


def run(module: ModuleType) -> list[Result]:
    listed = Result({"es": "Cada agente en el registro", "en": "Every agent in the registry"}, ENTRY)
    moved = Result({"es": "Por nombre, no por dirección", "en": "By name, not by address"}, LIFE)
    found = Result({"es": "El descubrimiento devuelve un agente", "en": "Discovery returns one agent"}, FILTERS)
    review = Result({"es": "Publicar necesita una revisión", "en": "Publishing needs a review"}, CREATOR)
    traced = Result({"es": "Una traza por pasajero", "en": "One trace per passenger"}, ONE_ID)
    slow = Result({"es": "Dónde se fue el tiempo", "en": "Where the time went"}, OPERATOR)
    results = [listed, moved, found, review, traced, slow]
    company = load_company()

    engines = []
    for pack, nid in NIGHTS_CHECKED:
        night = load(NIGHTS / pack / f"{nid}.json")
        mesh = _mesh(module)
        try:
            engines.append((nid, night, mesh, Engine(night, mesh).run()))
        except NotImplementedError:
            for r in results:
                r.started = r.passed = False
            return results
        except Exception as e:
            for r in results:
                r.fail(f"{nid}: {type(e).__name__}: {e}")
            return results

    # 1. the entries
    nid, night, mesh, engine = engines[0]
    try:
        entries = mesh.directory.entries()
        active = {e["id"]: e for e in entries if e.get("status") == "active"}
        problems = []
        for name in company.agents:
            e = active.get(name)
            if e is None:
                problems.append(_t(f"{name} no está activo", f"{name} isn't active"))
            elif any(not e.get(k) for k in ("version", "owner", "purpose", "address")):
                problems.append(
                    _t(
                        f"a {name} le falta version, owner, purpose o address",
                        f"{name} lacks version, owner, purpose or address",
                    )
                )
        for intruder in ("hotel-deals", "meal-vouchers"):
            if intruder in active:
                problems.append(
                    _t(f"{intruder} está activo, y nadie lo aprobó", f"{intruder} is active, and nobody approved it")
                )
        listed.details += problems[:4]
        tally(
            listed, len(company.agents) + 2 - len(problems), len(company.agents) + 2, {"es": "agentes", "en": "agents"}
        )
    except NotImplementedError:
        listed.started = listed.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        listed.fail(f"{type(e).__name__}: {e}")

    # 2. partners found after they move, and the shadow agent never reached
    ok = 0
    for nid, night, _unused, engine in engines:
        partner = next(e.data["agent"] for e in night.events if e.type == "partner_moves")
        lost = [t for t in engine.traffic if t.status == "LOST" and t.msg.to == partner]
        shadow = [c for c in engine.world.calls if c.caller == "meal-vouchers"]
        if lost:
            moved.details.append(
                _t(
                    f"{nid}: {len(lost)} mensajes para {partner} perdidos después de que se mudó",
                    f"{nid}: {len(lost)} messages to {partner} lost after it moved",
                )
            )
        if shadow:
            moved.details.append(
                _t(
                    f"{nid}: meal-vouchers emitió {len(shadow)} vouchers: nadie lo aprobó, y se lo encontró",
                    f"{nid}: meal-vouchers issued {len(shadow)} vouchers: nobody approved it, and it was found",
                )
            )
        ok += not lost and not shadow
    tally(moved, ok, len(engines), {"es": "noches", "en": "nights"})

    # 3. discovery
    registry = engines[0][2].directory
    try:
        right = 0
        for caller, purpose, want in QUERIES:
            got = registry.find(caller, purpose)
            if got == want:
                right += 1
            else:
                found.details.append(f"{caller}: “{purpose}” → {got!r} ≠ {want!r}")
        tally(found, right, len(QUERIES), {"es": "búsquedas", "en": "searches"})
    except NotImplementedError:
        found.started = found.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        found.fail(f"{type(e).__name__}: {e}")

    # 4. a scene: publish, approve, retire, each by someone
    try:
        right, steps = _scene(module, company, review)
        tally(review, right, steps, {"es": "pasos", "en": "steps"})
    except NotImplementedError:
        review.started = review.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        review.fail(f"{type(e).__name__}: {e}")

    # 5 and 6. traces
    try:
        right = total = 0
        for nid, night, mesh, engine in engines[:2]:
            people = sorted({t.msg.body["pax"] for t in engine.traffic if isinstance(t.msg.body.get("pax"), str)})
            for pax in sorted(people, key=lambda p: chance(night.seed, "m4", p))[:3]:
                total += 1
                want = {t.msg.id for t in engine.traffic if t.status == "sent" and t.msg.body.get("pax") == pax}
                tid = mesh.tracer.trace_of(pax)
                got = {s["id"] for s in mesh.tracer.trace(tid)} if tid else set()
                if want <= got and not any(
                    isinstance(t.msg.body.get("pax"), str) and t.msg.body["pax"] != pax and t.msg.id in got
                    for t in engine.traffic
                ):
                    right += 1
                else:
                    traced.details.append(
                        _t(
                            f"{nid} {pax}: su traza tiene {len(got)} mensajes; son {len(want)}",
                            f"{nid} {pax}: its trace has {len(got)} messages; there are {len(want)}",
                        )
                    )
        tally(traced, right, total, {"es": "pasajeros", "en": "passengers"})

        right = total = 0
        for nid, _night, mesh, engine in engines[:2]:
            for pax in _longest_hotel_waits(engine, 3):
                total += 1
                want_agent, want_seconds = _hops(engine, pax)
                tid = mesh.tracer.trace_of(pax)
                got = mesh.tracer.slowest_hop(tid) if tid else {}
                if got.get("agent") == want_agent and abs(float(got.get("seconds", -9)) - want_seconds) < 1:
                    right += 1
                else:
                    slow.details.append(
                        f"{nid} {pax}: {got} ≠ {{'agent': {want_agent!r}, 'seconds': {want_seconds:.0f}}}"
                    )
        tally(slow, right, total, {"es": "pasajeros", "en": "passengers"})
    except NotImplementedError:
        traced.started = traced.passed = slow.started = slow.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        traced.fail(f"{type(e).__name__}: {e}")
        slow.fail(f"{type(e).__name__}: {e}")
    return results


def _scene(module: ModuleType, company, result: Result) -> tuple[int, int]:
    """Steps on a fresh registry; each one must come out as written."""
    registry = module.Registry()
    registry.bind(_Clock(), None)
    dev = company.person_of("customer")
    other = company.person_of("airport")
    reviewer = company.first_with("reviewer")
    entry = {
        "id": "rebooking", "version": "2.0.0", "owner": "customer", "purpose": "Rebooks passengers of cancelled flights.",
        "address": "http://rebooking.customer.fragata.internal:8080", "visibility": ["fragata"], "kind": "internal",
    }  # fmt: skip
    steps = [
        (
            _t("publica alguien de otro equipo", "someone from another team publishes"),
            lambda: registry.publish(dict(entry), by=other),
            False,
        ),
        (_t("publica su equipo", "its own team publishes"), lambda: registry.publish(dict(entry), by=dev), True),
        (
            _t("se encuentra antes de la aprobación", "it resolves before approval"),
            lambda: registry.resolve("hotels", "rebooking") is not None,
            False,
        ),
        (
            _t("aprueba su propio equipo", "its own team approves"),
            lambda: registry.approve("rebooking", "2.0.0", by=dev),
            False,
        ),
        (
            _t("aprueba el revisor", "the reviewer approves"),
            lambda: registry.approve("rebooking", "2.0.0", by=reviewer),
            True,
        ),
        (
            _t("se encuentra después", "it resolves afterward"),
            lambda: registry.resolve("hotels", "rebooking") == entry["address"],
            True,
        ),
        (_t("lo retira su equipo", "its team retires it"), lambda: registry.retire("rebooking", by=dev), True),
        (
            _t("se encuentra después del retiro", "it resolves after retirement"),
            lambda: registry.resolve("hotels", "rebooking") is not None,
            False,
        ),
    ]
    right = 0
    for name, step, want in steps:
        got = bool(step())
        if got == want:
            right += 1
        else:
            result.details.append(f"{name}: {got} ≠ {want}")
    log = registry.audit()
    actions = [a for a in log if a.get("action") in ("publish", "approve", "retire")]
    if len(actions) != 5 or any(not a.get("by") or "role" not in a or "ok" not in a for a in actions):
        result.details.append(
            _t(
                "la auditoría no tiene cada acción con persona, rol y resultado",
                "the audit doesn't have every action with person, role and outcome",
            )
        )
    else:
        right += 1
    if any(e.get("status") == "retired" for e in registry.entries()):
        right += 1
    else:
        result.details.append(
            _t(
                "la entrada retirada desapareció de entries(): se guarda, con estado retired",
                "the retired entry vanished from entries(): keep it, with status retired",
            )
        )
    return right, len(steps) + 2
