"""Checks for milestone 7, the next storm.

Your factory builds the entry-rules agent, your pipeline puts it (and two bad versions) through
its gates, your retirement is tried on the duplicate hotel agent, and the agent you built runs in
the final pack with the reference parts of every other milestone.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import ModuleType

from .. import NIGHTS
from ..agents.planned import planned_rebooking
from ..company import can_enter, load_company
from ..i18n import lang
from ..mesh import ALLOW, Mesh
from ..mesh.naive import build as naive
from ..milestones import Lesson
from ..night.model import load
from ..score import score
from ..sdk import Agent
from ..sim.engine import Engine
from .core import Result, guard, reference, tally


def _l(slug: str, es: tuple[str, str], en: tuple[str, str]) -> Lesson:
    return Lesson(slug, {"es": es, "en": en})


TEMPLATE = _l(
    "agent-factory",
    ("Plantillas: empezar desde un agente conocido", "plantillas-empezar-desde-un-agente-conocido"),
    ("Templates: start from a known agent", "templates-start-from-a-known-agent"),
)
PIPELINE = _l(
    "agent-factory",
    ("El pipeline: cada cambio pasa los mismos controles", "el-pipeline-cada-cambio-pasa-los-mismos-controles"),
    ("The pipeline: every change passes the same gates", "the-pipeline-every-change-passes-the-same-gates"),
)
STAGES = _l(
    "agent-lifecycle",
    ("Siete etapas, siete controles", "siete-etapas-siete-controles"),
    ("Seven stages, seven gates", "seven-stages-seven-gates"),
)
RETIRE = _l(
    "agent-lifecycle",
    ("Retirar un agente con seguridad", "retirar-un-agente-con-seguridad"),
    ("Retiring an agent safely", "retiring-an-agent-safely"),
)
ECOSYSTEM = _l(
    "agent-adoption-roadmap", ("T4: un ecosistema", "t4-un-ecosistema"), ("Q4: an ecosystem", "q4-an-ecosystem")
)
RIGHTS = _l(
    "agent-operating-model",
    ("Estructura: derechos de decisión", "estructura-derechos-de-decisión"),
    ("Structure: decision rights", "structure-decision-rights"),
)
GATES = ("tests", "benchmark", "security", "certification")
FINAL_BAR = 0.95


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


class _Env:
    def __init__(self) -> None:
        self.now = 60_000.0

    def version_of(self, agent: str) -> str:
        return "1.0.0"

    def quarantine(self, agent: str, reason: str) -> None:
        pass

    def release(self, agent: str) -> None:
        pass


class _Open:
    def bind(self, env, mesh):
        pass

    def check(self, call):
        return ALLOW


def _registry_and_trust():
    env = _Env()
    registry, trust = reference("4").Registry(), reference("6").TrustGate(_Open())
    registry.bind(env, None)
    trust.bind(env, Mesh("x", registry, None, None, None, None, None))
    return registry, trust


def _full_mesh() -> Mesh:
    m3, m4, m5, m6 = (reference(n) for n in "3456")
    workspace = m3.Workspace()
    return Mesh("full", m4.Registry(), workspace, workspace, m5.Identity(), m6.TrustGate(m5.Gate()), m4.Tracer())


def _known_answers() -> list[tuple[dict, dict]]:
    night = load(NIGHTS / "practice" / "p1.json")
    out = []
    for match in (
        lambda p: p.passport_group == 1 and not p.local,
        lambda p: p.passport_group == 2 and p.visa,
        lambda p: p.passport_group == 2 and not p.visa,
        lambda p: p.passport_group == 3,
    ):
        p = next(p for p in night.passengers if match(p))
        out.append(({"pax": p.id}, {"pax": p.id, "may_enter": can_enter(p)}))
    return out


def _lenient(body, ctx):
    return {"pax": body["pax"], "may_enter": True}


def run(module: ModuleType) -> list[Result]:
    built = Result({"es": "De la plantilla al registro", "en": "From template to registry"}, TEMPLATE)
    stopped = Result({"es": "Un control frena una mala versión", "en": "A gate stops a bad version"}, PIPELINE)
    nobody = Result({"es": "Nadie va adonde no puede", "en": "Nobody sent where they can't go"}, STAGES)
    retired = Result({"es": "Retirar con seguridad", "en": "Retire safely"}, RETIRE)
    rights = Result({"es": "Quién decide qué", "en": "Who decides what"}, RIGHTS)
    storm = Result({"es": "La próxima tormenta", "en": "The next storm"}, ECOSYSTEM)
    results = [built, stopped, nobody, retired, rights, storm]

    try:
        candidate = module.entry_rules()
    except NotImplementedError:
        for r in results:
            r.started = r.passed = False
        return results
    except Exception as e:  # your code raised: report it, don't crash
        for r in results:
            r.fail(f"{type(e).__name__}: {e}")
        return results
    missing = [
        k
        for k in ("id", "version", "team", "purpose", "address", "cls", "needs", "tests", "contract")
        if k not in candidate
    ]
    if missing or not (isinstance(candidate.get("cls"), type) and issubclass(candidate["cls"], Agent)):
        for r in results:
            r.fail(
                _t("al candidato le falta: ", "the candidate lacks: ")
                + ", ".join(missing or ["cls (an Agent subclass)"])
            )
        return results

    # 1. through the pipeline, into the registry
    registry, trust = _registry_and_trust()
    try:
        report = module.pipeline(candidate, registry, trust)
    except NotImplementedError:
        for r in results:
            r.started = r.passed = False
        return results
    except Exception as e:  # your code raised: report it, don't crash
        for r in results:
            r.fail(f"{type(e).__name__}: {e}")
        return results
    gates = {g.get("gate"): g for g in report.get("gates", [])}
    problems = [
        f"{name}: {gates.get(name, {}).get('detail', _t('no corrió', 'didn’t run'))}"
        for name in GATES
        if not gates.get(name, {}).get("passed")
    ]
    active = [e for e in registry.entries() if e["id"] == candidate["id"] and e["status"] == "active"]
    certified = [c for c in trust.certifications() if c["agent"] == candidate["id"] and c["status"] == "active"]
    if problems:
        built.details += problems[:3]
    if not report.get("registered") or not active:
        built.details.append(_t("no quedó activo en el registro", "it isn't active in the registry"))
    if not certified:
        built.details.append(_t("no tiene una certificación activa", "it has no active certification"))
    tally(built, 4 - len(problems) + bool(active) + bool(certified), 6, {"es": "pasos", "en": "steps"})

    # 2. two bad versions
    from .m7_bad import nosy_decide

    right = 0
    spec = dict(candidate["cls"].spec, tests=_known_answers())
    for name, decide, want_gate in (
        (_t("deja salir a todos", "lets everyone out"), _lenient, "tests"),
        (
            _t("llama a un sistema que no declaró", "calls a system it didn't declare"),
            nosy_decide(candidate["cls"]),
            "security",
        ),
    ):
        reg, tr = _registry_and_trust()
        try:
            bad = module.new_agent(dict(spec, version="1.0.1"), decide)
            got = module.pipeline(bad, reg, tr)
        except Exception as e:
            stopped.details.append(f"{name}: {type(e).__name__}: {e}")
            continue
        failed = [g.get("gate") for g in got.get("gates", []) if not g.get("passed")]
        if not got.get("registered") and failed[:1] == [want_gate]:
            right += 1
        else:
            stopped.details.append(
                _t(f"{name}: registrado={got.get('registered')}, falló {failed or 'nada'} (esperado: {want_gate})",
                   f"{name}: registered={got.get('registered')}, failed {failed or 'nothing'} (expected: {want_gate})")
            )  # fmt: skip
    tally(stopped, right, 2, {"es": "versiones", "en": "versions"})

    # 3. in real nights, hotels asks it before booking
    right = 0
    for nid in ("p1", "p2"):
        night = load(NIGHTS / "practice" / f"{nid}.json")
        engine = Engine(night, _full_mesh(), new_agents=[candidate]).run()
        sent = [
            p for p, stays in engine.world.stays.items()
            if any(s.kind == "room" and s.by == "hotels" for s in stays) and not can_enter(night.passenger(p))
        ]  # fmt: skip
        errors = [line for line in engine.agent_logs.get(candidate["id"], []) if "ERROR" in line]
        asked = sum(1 for t in engine.traffic if t.msg.to == candidate["id"])
        if sent or errors or not asked:
            nobody.details.append(
                _t(f"{nid}: {len(sent)} enviados por hotels adonde no pueden ir, {len(errors)} errores, {asked} consultas",
                   f"{nid}: {len(sent)} sent by hotels where they can't go, {len(errors)} errors, {asked} questions asked")
            )  # fmt: skip
        else:
            right += 1
    tally(nobody, right, 2, {"es": "noches", "en": "nights"})

    # 4. retire the duplicate hotel agent
    try:
        right = _retire_scene(module, retired)
        tally(retired, right, 4, {"es": "pasos", "en": "steps"})
    except NotImplementedError:
        retired.started = retired.passed = False
    except Exception as e:  # your code raised: report it, don't crash
        retired.fail(f"{type(e).__name__}: {e}")

    # 5. who decides what
    if hasattr(module, "operating_model"):
        ok, model = guard(rights, module.operating_model)
        if ok and isinstance(model, dict):
            right, total = _decision_rights(model, rights)
            tally(rights, right, total, {"es": "reglas", "en": "rules"})
    else:
        rights.started = rights.passed = False

    # 6. the final pack
    m2 = reference("2")
    right = 0
    for path in sorted((NIGHTS / "final").glob("*.json")):
        night = load(path)
        engine = Engine(night, _full_mesh(), agents={"rebooking": planned_rebooking(m2)}, new_agents=[candidate]).run()
        board = score(engine)
        share = board.rehoused / board.total
        if share >= FINAL_BAR:
            right += 1
        else:
            storm.details.append(f"{night.id}: {share:.1%} < {FINAL_BAR:.0%}")
    total = len(list((NIGHTS / "final").glob("*.json")))
    tally(storm, right, total, {"es": "noches finales", "en": "final nights"})
    return results


def _retire_scene(module: ModuleType, result: Result) -> int:
    company = load_company()
    owner = company.person_of("digital")
    registry, trust = _registry_and_trust()
    m4 = reference("4")
    entry = {
        "id": "lodging", "version": "1.0.0", "owner": "digital", "purpose": "Books a hotel from the app when the passenger asks.",
        "address": "http://lodging.digital.fragata.internal:8080", "visibility": ["fragata"], "kind": "internal",
    }  # fmt: skip
    registry.publish(entry, by=owner)
    registry.approve("lodging", "1.0.0", by=company.first_with("reviewer"))
    trust.certify("lodging", "1.0.0", by=company.first_with("certifier"), evidence={"tests": "passed"})
    del m4
    right = 0
    with tempfile.TemporaryDirectory() as tmp:
        engine = Engine(load(NIGHTS / "practice" / "p1.json"), naive()).run()
        engine.write_logs(Path(tmp) / "p1")
        log = Path(tmp) / "p1" / "traffic.log"
        first = module.retire("lodging", log, registry, trust, by=owner)
        if not first.get("retired") and {"app", "priority"} <= set(first.get("callers", [])):
            right += 1
        else:
            result.details.append(_t(f"con llamadas todavía: {first}", f"with callers still: {first}"))
        moved = Path(tmp) / "moved.log"
        address = load_company().agents["lodging"].address
        moved.write_text(
            "\n".join(
                line
                for line in log.read_text().splitlines()
                if "-> lodging " not in line and f"-> {address} " not in line
            )
            + "\n"
        )
        second = module.retire("lodging", moved, registry, trust, by=owner)
        if second.get("retired"):
            right += 1
        else:
            result.details.append(
                _t(f"sin llamadas no se retiró: {second}", f"with no callers it wasn't retired: {second}")
            )
    statuses = [e["status"] for e in registry.entries() if e["id"] == "lodging"]
    if statuses == ["retired"]:
        right += 1
    else:
        result.details.append(
            _t(
                f"en el registro: {statuses} (se guarda la entrada, retirada)",
                f"in the registry: {statuses} (keep the entry, retired)",
            )
        )
    if not any(c["agent"] == "lodging" and c["status"] == "active" for c in trust.certifications()):
        right += 1
    else:
        result.details.append(_t("su certificación sigue activa", "its certification is still active"))
    return right


def _decision_rights(model: dict, result: Result) -> tuple[int, int]:
    """Each decision belongs to someone with the right role, and nobody checks their own work."""
    people = load_company().people

    def role(decision: str) -> str | None:
        return people.get(model.get(decision, ""), {}).get("role")

    def team(decision: str) -> str | None:
        return people.get(model.get(decision, ""), {}).get("team")

    unknown = [
        d for d in ("asks", "builds", "approves", "certifies", "on_call", "retires") if model.get(d) not in people
    ]
    rules = [
        (_t("cada decisión tiene una persona de company/people.toml", "every decision has a person from company/people.toml"), not unknown),
        (_t("pide y construye el equipo de Aeropuerto", "Airport asks for it and builds it"), team("asks") == "airport" and team("builds") == "airport"),
        (_t("aprueba un revisor", "a reviewer approves"), role("approves") == "reviewer"),
        (_t("certifica un certificador", "a certifier certifies"), role("certifies") == "certifier"),
        (_t("de guardia está la persona de guardia", "the person on duty is on call"), role("on_call") == "duty"),
        (_t("quien lo construye no lo aprueba ni lo certifica", "whoever builds it neither approves nor certifies it"),
         model.get("builds") not in (model.get("approves"), model.get("certifies"))),
    ]  # fmt: skip
    right = 0
    for name, ok in rules:
        if ok:
            right += 1
        else:
            result.details.append(name)
    return right, len(rules)
