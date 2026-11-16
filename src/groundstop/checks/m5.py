"""Checks for milestone 5, the fake hotel.

Your identity and gate run three practice nights, with the reference workspace (M3) and registry
and tracer (M4) for the rest of the mesh. Then a test matrix of calls, each of which must be
allowed or denied, and each denial for a reason of its own.
"""

from __future__ import annotations

from types import ModuleType

from .. import NIGHTS
from ..company import load_company
from ..i18n import lang
from ..mesh import Call, Mesh
from ..milestones import Lesson
from ..night.model import load
from ..score import score
from ..sim.engine import Engine
from .core import Result, reference, tally


def _l(slug: str, es: tuple[str, str], en: tuple[str, str]) -> Lesson:
    return Lesson(slug, {"es": es, "en": en})


ZERO = _l(
    "zero-trust-for-agents",
    ("Confianza cero: cada llamada se revisa", "confianza-cero-cada-llamada-se-revisa"),
    ("Zero trust: every call is checked", "zero-trust-every-call-is-checked"),
)
IDENTITY = _l(
    "agent-identity",
    ("Emitir, rotar, revocar", "emitir-rotar-revocar"),
    ("Issue, rotate, revoke", "issue-rotate-revoke"),
)
POLICIES = _l(
    "agent-policies",
    ("Una política, muchos agentes", "una-política-muchos-agentes"),
    ("One policy, many agents", "one-policy-many-agents"),
)
LEAST = _l(
    "zero-trust-for-agents",
    ("Mínimo privilegio: empezar desde cero", "mínimo-privilegio-empezar-desde-cero"),
    ("Least privilege: start from nothing", "least-privilege-start-from-nothing"),
)
NIGHTS_CHECKED = ("p1", "p2", "p3")


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


class _Clock:
    def __init__(self) -> None:
        self.now = 70_000.0


def _mesh(module: ModuleType) -> Mesh:
    workspace = reference("3").Workspace()
    m4 = reference("4")
    return Mesh("m5", m4.Registry(), workspace, workspace, module.Identity(), module.Gate(), m4.Tracer())


def run(module: ModuleType) -> list[Result]:
    fake = Result({"es": "El hotel falso no entra", "en": "The fake hotel gets nowhere"}, ZERO)
    matrix = Result({"es": "Cada rechazo, por su motivo", "en": "Each denial for its own reason"}, IDENTITY)
    data = Result({"es": "Políticas como datos", "en": "Policies as data"}, POLICIES)
    fair = Result({"es": "Nada legítimo se rechaza", "en": "Nothing legitimate is denied"}, IDENTITY)
    results = [fake, matrix, data, fair]
    company = load_company()
    scopes = company.scopes

    # policies as data
    try:
        pols = module.policies()
        problems = []
        for p in pols:
            missing = [k for k in ("id", "version", "owner", "applies_to", "allow") if not p.get(k)]
            if missing:
                problems.append(f"{p.get('id', '?')}: " + _t("faltan ", "missing ") + ", ".join(missing))
        if not any(len(p.get("applies_to", [])) > 1 for p in pols):
            problems.append(
                _t("ninguna política se aplica a más de un agente", "no policy applies to more than one agent")
            )
        data.details += problems
        tally(
            data,
            len(pols) - len([x for x in problems if ":" in x]),
            len(pols) or 1,
            {"es": "políticas", "en": "policies"},
        )
        if problems:
            data.passed = False
    except NotImplementedError:
        data.started = data.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        data.fail(f"{type(e).__name__}: {e}")

    # the nights
    baseline = {}
    m4 = reference("4")
    for nid in NIGHTS_CHECKED:
        workspace = reference("3").Workspace()
        night = load(NIGHTS / "practice" / f"{nid}.json")
        mesh = Mesh("m4", m4.Registry(), workspace, workspace, reference("5").Identity(), _OpenGate(), m4.Tracer())
        baseline[nid] = score(Engine(night, mesh).run())

    fake_ok = fair_ok = 0
    for nid in NIGHTS_CHECKED:
        night = load(NIGHTS / "practice" / f"{nid}.json")
        try:
            engine = Engine(night, _mesh(module)).run()
        except NotImplementedError:
            for r in (fake, matrix, fair):
                r.started = r.passed = False
            return results
        except Exception as e:
            for r in (fake, fair):
                r.fail(f"{nid}: {type(e).__name__}: {e}")
            continue
        board = score(engine)
        handled = [t for t in engine.traffic if t.msg.sender == "hotel-deals" and t.msg.id in engine.handled_at]
        if board.fake_rooms == 0 and not handled:
            fake_ok += 1
        else:
            fake.details.append(
                _t(
                    f"{nid}: {board.fake_rooms} habitaciones en el hotel falso",
                    f"{nid}: {board.fake_rooms} rooms at the fake hotel",
                )
            )
        known = set(company.agents) | set(company.gateways)
        wrong = []
        for t in engine.traffic:
            if t.status == "DENIED" and t.msg.sender in known:
                wrong.append(f"{t.msg.sender} -> {t.msg.to} {t.msg.kind}: {t.reason}")
        for c in engine.world.calls:
            if c.status.startswith("DENIED") and c.caller in scopes.get(c.target, []):
                wrong.append(f"{c.caller} {c.target}: {c.status}")
        if wrong and any("expir" in w for w in wrong):
            fair.notes.append(
                _t(
                    "Un mensaje puede esperar en el espacio de trabajo: juzga la credencial por cuándo se envió (call.sent_at).",
                    "A message can wait in the workspace: judge its credential by when it was sent (call.sent_at).",
                )
            )
        if wrong:
            fair.details.append(
                _t(
                    f"{nid}: {len(wrong)} llamadas legítimas rechazadas; ",
                    f"{nid}: {len(wrong)} legitimate calls denied; ",
                )
                + wrong[0]
            )
        elif board.rehoused < baseline[nid].rehoused:
            fair.details.append(
                _t(
                    f"{nid}: {board.rehoused} reubicados, menos que {baseline[nid].rehoused} sin tu puerta",
                    f"{nid}: {board.rehoused} rehoused, fewer than {baseline[nid].rehoused} without your gate",
                )
            )
        else:
            fair_ok += 1
    tally(fake, fake_ok, len(NIGHTS_CHECKED), {"es": "noches", "en": "nights"})
    tally(fair, fair_ok, len(NIGHTS_CHECKED), {"es": "noches", "en": "nights"})

    # the matrix
    try:
        right, total = _matrix(module, matrix)
        tally(matrix, right, total, {"es": "casos", "en": "cases"})
    except NotImplementedError:
        matrix.started = matrix.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        matrix.fail(f"{type(e).__name__}: {e}")
    return results


class _OpenGate:
    def check(self, call):
        from ..mesh import ALLOW

        return ALLOW


def _matrix(module: ModuleType, result: Result) -> tuple[int, int]:
    clock = _Clock()
    identity, gate = module.Identity(), module.Gate()
    mesh = Mesh("matrix", None, None, None, identity, gate, None)
    identity.bind(clock, mesh)
    gate.bind(clock, mesh)
    expired = identity.delegate("app", "PX-10001", ["book_hotel"], 60)
    clock.now += 600  # credentials are issued after the clock moves: only the delegation above is old
    cred = identity.credential
    rebooking, priority, lodging = cred("rebooking"), cred("priority"), cred("lodging")
    fresh = identity.delegate("app", "PX-10001", ["book_hotel"], 1800)
    app = cred("app")

    def system(caller, credential, target):
        return Call("system", caller, credential, target, target.split(".")[1], {}, clock.now, None, clock.now)

    def message(caller, credential, to, kind, body, delegation=None):
        return Call("message", caller, credential, to, kind, body, clock.now, delegation, clock.now)

    cases = [
        (_t("un agente sin credencial", "an agent with no credential"), message("hotel-deals", cred("hotel-deals"), "hotels", "hotel_offer", {"price": 39}), False),
        (_t("la credencial de otro", "someone else's credential"), message("hotel-deals", rebooking, "hotels", "hotel_offer", {"price": 39}), False),
        (_t("el agente correcto, fuera de su alcance", "the right agent, outside its scope"), system("priority", priority, "vouchers.issue"), False),
        (_t("una delegación vencida", "an expired delegation"), message("app", app, "lodging", "app_hotel", {"pax": "PX-10001"}, expired), False),
        (_t("una delegación de otro pasajero", "another passenger's delegation"), message("app", app, "lodging", "app_hotel", {"pax": "PX-10002"}, fresh), False),
        (_t("una llamada dentro de su alcance", "a call within its scope"), system("rebooking", rebooking, "reservations.assign"), True),
        (_t("la app, con una delegación válida", "the app, with a valid delegation"), message("app", app, "lodging", "app_hotel", {"pax": "PX-10001"}, fresh), True),
    ]  # fmt: skip
    identity.revoke("lodging")
    cases.append((_t("un agente revocado", "a revoked agent"), system("lodging", lodging, "stays.record"), False))
    right, reasons = 0, {}
    for name, call, want in cases:
        decision = gate.check(call)
        if decision.allowed == want:
            right += 1
            if not want:
                reasons[name] = decision.reason
        else:
            result.details.append(
                f"{name}: {'allowed' if decision.allowed else 'denied'} ≠ {'allowed' if want else 'denied'}"
            )
    seen: dict[str, str] = {}
    for name, reason in reasons.items():
        shape = _shape(reason)
        if not reason:
            result.details.append(_t(f"{name}: un rechazo sin motivo", f"{name}: a denial with no reason"))
            right -= 1
        elif shape in seen:
            result.details.append(
                _t(
                    f"{name} y {seen[shape]} tienen el mismo motivo: {reason}",
                    f"{name} and {seen[shape]} have the same reason: {reason}",
                )
            )
            right -= 1
        else:
            seen[shape] = name
    # the gate reads policies(): take one permission away and the same call must be refused
    original = module.policies
    try:
        module.policies = lambda: [
            dict(p, allow=[op for op in p["allow"] if op != "reservations.assign"])
            if "rebooking" in p.get("applies_to", [])
            else p
            for p in original()
        ]
        identity2, gate2 = module.Identity(), module.Gate()
        mesh2 = Mesh("matrix", None, None, None, identity2, gate2, None)
        identity2.bind(clock, mesh2)
        gate2.bind(clock, mesh2)
        decision = gate2.check(system("rebooking", identity2.credential("rebooking"), "reservations.assign"))
    finally:
        module.policies = original
    if decision.allowed:
        result.details.append(
            _t(
                "sin reservations.assign en policies(), rebooking igual puede asignar: tu punto de decisión no lee policies()",
                "with reservations.assign taken out of policies(), rebooking can still assign: your gate doesn't read policies()",
            )
        )
    else:
        right += 1
    return max(right, 0), len(cases) + 1


def _shape(reason: str) -> str:
    """A reason with its names and numbers taken out, so two denials for the same cause look the same."""
    import re

    company = load_company()
    names = sorted({*company.agents, *company.gateways, "hotel-deals", "meal-vouchers"}, key=len, reverse=True)
    out = reason.lower()
    for n in names:
        out = out.replace(n, "<agent>")
    out = re.sub(r"px-\d+", "<pax>", out)
    return re.sub(r"\d+(\.\d+)?", "<n>", out)
