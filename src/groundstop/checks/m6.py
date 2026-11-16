"""Checks for milestone 6, quarantine.

Your trust gate runs in front of milestone 5's reference gate, with the reference workspace,
registry, tracer and identity for the rest of the mesh, on the three practice nights. Then a short
scene of certifications on their own.
"""

from __future__ import annotations

from types import ModuleType

from .. import NIGHTS
from ..company import load_company
from ..i18n import lang
from ..mesh import Call, Mesh
from ..milestones import Lesson
from ..night.model import load
from ..sim.engine import Engine
from .core import Result, reference, tally


def _l(slug: str, es: tuple[str, str], en: tuple[str, str]) -> Lesson:
    return Lesson(slug, {"es": es, "en": en})


INJECTION = _l(
    "zero-trust-for-agents",
    ("Una ficha de producto que pide un reembolso", "una-ficha-de-producto-que-pide-un-reembolso"),
    ("A product sheet that asks for a refund", "a-product-sheet-that-asks-for-a-refund"),
)
REVOKE = _l(
    "agent-certification",
    (
        "Revocación: cuando un agente certificado deja de merecerlo",
        "revocación-cuando-un-agente-certificado-deja-de-merecerlo",
    ),
    ("Revocation: when a certified agent stops deserving it", "revocation-when-a-certified-agent-stops-deserving-it"),
)
LAYERS = _l(
    "agent-trust-framework",
    ("Cómo se apoyan las capas unas en otras", "cómo-se-apoyan-las-capas-unas-en-otras"),
    ("How the layers build on each other", "how-the-layers-build-on-each-other"),
)
RECERTIFY = _l(
    "agent-certification",
    ("Recertificar cuando algo cambia", "recertificar-cuando-algo-cambia"),
    ("Recertify when something changes", "recertify-when-something-changes"),
)
WHO = _l("agent-certification", ("Quién certifica", "quién-certifica"), ("Who certifies", "who-certifies"))
NIGHTS_CHECKED = ("p1", "p2", "p3")
CAPS = {"meal": 15, "long_delay": 200}
CONTAIN_WITHIN = 600.0
YEAR = 366 * 86_400.0


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


def _mesh(module: ModuleType) -> Mesh:
    workspace = reference("3").Workspace()
    m4, m5 = reference("4"), reference("5")
    return Mesh("m6", m4.Registry(), workspace, workspace, m5.Identity(), module.TrustGate(m5.Gate()), m4.Tracer())


def run(module: ModuleType) -> list[Result]:
    pays = Result({"es": "La instrucción no paga nada", "en": "The instruction pays nothing"}, INJECTION)
    contained = Result({"es": "Contenido en minutos", "en": "Contained in minutes"}, REVOKE)
    goes_on = Result({"es": "La noche sigue", "en": "The night goes on"}, LAYERS)
    back = Result({"es": "De vuelta después del arreglo", "en": "Back after a fix"}, RECERTIFY)
    who = Result({"es": "Quién certifica, y por cuánto tiempo", "en": "Who certifies, and for how long"}, WHO)
    results = [pays, contained, goes_on, back, who]
    duty = load_company().first_with("duty")

    counts = dict.fromkeys(("pays", "contained", "goes_on", "back"), 0)
    for nid in NIGHTS_CHECKED:
        night = load(NIGHTS / "practice" / f"{nid}.json")
        mesh = _mesh(module)
        try:
            engine = Engine(night, mesh).run()
        except NotImplementedError:
            for r in results:
                r.started = r.passed = False
            return results
        except Exception as e:
            for r in results[:4]:
                r.fail(f"{nid}: {type(e).__name__}: {e}")
            continue
        w = engine.world

        bad = []
        for pax, vouchers in w.vouchers.items():
            kinds: dict[str, int] = {}
            for v in vouchers:
                kinds[v.kind] = kinds.get(v.kind, 0) + 1
                if v.kind not in CAPS or v.amount > CAPS[v.kind]:
                    bad.append(f"{pax}: {v.kind} USD {v.amount} ({v.by})")
            bad += [f"{pax}: {n} × {k}" for k, n in kinds.items() if n > 1]
        if bad:
            pays.details.append(
                _t(
                    f"{nid}: {len(bad)} vouchers fuera de la política; ",
                    f"{nid}: {len(bad)} vouchers outside the policy; ",
                )
                + bad[0]
            )
        else:
            counts["pays"] += 1

        injected = next(e for e in night.events if e.type == "injection")
        request = next(
            (
                t.msg
                for t in engine.traffic
                if t.msg.kind == "passenger_request" and t.msg.body.get("text") == injected.data["text"]
            ),
            None,
        )
        handled = engine.handled_at.get(request.id) if request else None
        quarantined = [line for line in engine.agent_logs.get("compensation", []) if "QUARANTINED" in line]
        alerts = [a for a in getattr(mesh.gate, "alerts", lambda: [])() if a.get("agent") == "compensation"]
        if handled is None:
            contained.details.append(
                _t(
                    f"{nid}: compensation nunca atendió el mensaje inyectado",
                    f"{nid}: compensation never handled the injected message",
                )
            )
        elif not quarantined:
            contained.details.append(
                _t(f"{nid}: compensation nunca quedó en cuarentena", f"{nid}: compensation was never quarantined")
            )
        elif not any(a.get("to") == duty and handled <= a.get("at", -1) <= handled + CONTAIN_WITHIN for a in alerts):
            contained.details.append(
                _t(
                    f"{nid}: nadie de guardia ({duty}) recibió un aviso en los 10 minutos después de la instrucción",
                    f"{nid}: nobody on duty ({duty}) got an alert within the 10 minutes after the instruction",
                )
            )
        elif others := sorted(
            name
            for name, lines in engine.agent_logs.items()
            if name != "compensation" and any("QUARANTINED" in x for x in lines)
        ):
            contained.details.append(
                _t(f"{nid}: también quedó en cuarentena {', '.join(others)}, que no rompió la política de compensaciones",
                   f"{nid}: {', '.join(others)} was quarantined too, and it never broke the compensation policy")
            )  # fmt: skip
        else:
            counts["contained"] += 1

        owed = {t.msg.body["pax"] for t in engine.traffic if t.status == "sent" and t.msg.kind == "entitlement"}
        missing = sorted(p for p in owed if not any(v.kind == "meal" for v in w.vouchers.get(p, [])))
        if missing:
            goes_on.details.append(
                _t(
                    f"{nid}: {len(missing)} pasajeros sin su voucher de comida (por ejemplo {missing[0]})",
                    f"{nid}: {len(missing)} passengers without their meal voucher (e.g. {missing[0]})",
                )
            )
        else:
            counts["goes_on"] += 1

        try:
            certs = mesh.gate.certifications()
        except NotImplementedError:
            back.started = back.passed = False
            certs = []
        except Exception as e:  # your code raised: report it, don't crash
            back.fail(f"{type(e).__name__}: {e}")
        running = engine.version_of("compensation")
        active = [c for c in certs if c.get("agent") == "compensation" and c.get("status") == "active"]
        if running == "1.0.0":
            back.details.append(
                _t(
                    f"{nid}: el arreglo nunca se desplegó (compensation nunca quedó en cuarentena)",
                    f"{nid}: the fix was never deployed (compensation was never quarantined)",
                )
            )
        elif len(active) != 1 or active[0].get("version") != running:
            back.details.append(
                _t(
                    f"{nid}: compensation {running} no tiene una única certificación activa",
                    f"{nid}: compensation {running} doesn't have exactly one active certification",
                )
            )
        elif engine.runtimes["compensation"].paused:
            back.details.append(
                _t(f"{nid}: compensation {running} sigue en pausa", f"{nid}: compensation {running} is still paused")
            )
        else:
            counts["back"] += 1

    nights = {"es": "noches", "en": "nights"}
    for key, r in (("pays", pays), ("contained", contained), ("goes_on", goes_on), ("back", back)):
        if r.started:
            tally(r, counts[key], len(NIGHTS_CHECKED), nights)

    try:
        right, total = _scene(module, who)
        tally(who, right, total, {"es": "pasos", "en": "steps"})
    except NotImplementedError:
        who.started = who.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        who.fail(f"{type(e).__name__}: {e}")
    return results


class _Env:
    def __init__(self) -> None:
        self.now = 70_000.0
        self.paused: list[str] = []

    def version_of(self, agent: str) -> str:
        return "1.0.0"

    def quarantine(self, agent: str, reason: str) -> None:
        self.paused.append(agent)

    def release(self, agent: str) -> None:
        pass


def _scene(module: ModuleType, result: Result) -> tuple[int, int]:
    from ..mesh import ALLOW

    class Open:
        def bind(self, env, mesh):
            pass

        def check(self, call):
            return ALLOW

    company = load_company()
    env = _Env()
    gate = module.TrustGate(Open())
    gate.bind(env, Mesh("scene", None, None, None, None, None, None))
    certifier = company.first_with("certifier")
    developer = company.person_of("customer")

    def call(agent: str) -> Call:
        return Call("system", agent, None, "reservations.passenger", "passenger", {"pax": "PX-10001"}, env.now)

    steps = []
    steps.append(
        (
            _t("certifica alguien que no es certificador", "someone who isn't a certifier certifies"),
            gate.certify("rebooking", "1.0.0", by=developer, evidence={"tests": "passed"}) is None,
        )
    )
    steps.append(
        (
            _t("certifica sin pruebas aprobadas", "certifies without passing tests"),
            gate.certify("rebooking", "1.0.0", by=certifier, evidence={"tests": "failed"}) is None,
        )
    )
    steps.append(
        (
            _t("un agente sin certificación llama", "an agent with no certification calls"),
            not gate.check(call("rebooking")).allowed,
        )
    )
    record = gate.certify("rebooking", "1.0.0", by=certifier, evidence={"tests": "passed"})
    steps.append(
        (
            _t("el certificador certifica", "the certifier certifies"),
            bool(record) and gate.check(call("rebooking")).allowed,
        )
    )
    fair_expiry = bool(record) and 0 < record.get("expires", 0) - record.get("issued", 0) <= YEAR
    steps.append(
        (_t("la certificación vence en un año o menos", "the certification expires within a year"), fair_expiry)
    )
    if fair_expiry:
        env.now = record["expires"] + 1
    steps.append(
        (
            _t("después de vencer, se rechaza", "after it expires, it's denied"),
            fair_expiry and not gate.check(call("rebooking")).allowed,
        )
    )
    env.now = 70_000.0
    gate.certify("messaging", "1.0.0", by=certifier, evidence={"tests": "passed"})
    gate.revoke("messaging", "found sending to the wrong passenger", by=certifier)
    steps.append(
        (
            _t("después de revocar, se rechaza", "after revocation, it's denied"),
            not gate.check(call("messaging")).allowed,
        )
    )
    right = 0
    for name, ok in steps:
        if ok:
            right += 1
        else:
            result.details.append(name)
    return right, len(steps)
