"""Checks for milestone 2, a contract for rebooking.

An outside program calls your agent from its contract alone: it sends only the fields the
contract's input declares, in a sandbox with p1's flights, and checks every answer against the
contract's output. Your plans are checked as data before they run, your logs against your plans,
your conformance checker against five planted deviations, and your agent in a whole night.
"""

from __future__ import annotations

import copy
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .. import NIGHTS
from ..agents.planned import planned_rebooking
from ..i18n import lang
from ..mesh import build
from ..milestones import Lesson
from ..night.model import load, seat_ids
from ..plans import NO_SEAT, STEPS, StepTools, booking_result, option, request_for
from ..score import SEAT_PROBLEMS, score
from ..sim.engine import Engine
from ..util import chance
from .core import NotStarted, Result, attempt, tally

ENDPOINT = Lesson(
    "enterprise-grade-agents",
    {
        "es": ("Un endpoint al que llamar", "un-endpoint-al-que-llamar"),
        "en": ("A callable endpoint", "a-callable-endpoint"),
    },
)
TYPES = Lesson(
    "agent-types",
    {
        "es": (
            "Agentes orientados a tareas: entra una solicitud, sale un resultado",
            "agentes-orientados-a-tareas-entra-una-solicitud-sale-un-resultado",
        ),
        "en": ("Task-oriented agents: a request in, a result out", "task-oriented-agents-a-request-in-a-result-out"),
    },
)
PLAN = Lesson(
    "agent-explainability",
    {
        "es": ("El plan de tareas, por escrito", "el-plan-de-tareas-por-escrito"),
        "en": ("The task plan, written down", "the-task-plan-written-down"),
    },
)
SUBSTITUTION = Lesson(
    "agent-explainability",
    {
        "es": (
            "Sustitución de parámetros: de dónde sale cada valor",
            "sustitución-de-parámetros-de-dónde-sale-cada-valor",
        ),
        "en": (
            "Parameter substitution: where each value comes from",
            "parameter-substitution-where-each-value-comes-from",
        ),
    },
)
EXECUTION = Lesson(
    "agent-explainability",
    {
        "es": ("El log de ejecución: ¿siguió el plan?", "el-log-de-ejecución-siguió-el-plan"),
        "en": ("The execution log: did it follow the plan?", "the-execution-log-did-it-follow-the-plan"),
    },
)
CODE = Lesson(
    "specialized-agents",
    {
        "es": ("Pasar los pasos fijos a código", "pasar-los-pasos-fijos-a-código"),
        "en": ("Hand the fixed steps to code", "hand-the-fixed-steps-to-code"),
    },
)

KEYS = ("name", "version", "owner", "purpose", "type", "input", "output", "limits")
TYPES_OF_AGENT = ("task-oriented", "goal-oriented", "observer", "simulation")
TELLS = ("agent:messaging", "agent:baggage", "agent:hotels", "agent:compensation")
SAMPLE = 60


def _t(es: str, en: str) -> str:
    return es if lang() == "es" else en


# ---- the sandbox the outside program calls your agent in -----------------------------------------


class SandboxTools(StepTools):
    """p1's flights, without the rest of the night: half the extra flights have their crew."""

    def __init__(self, night) -> None:
        self.night = night
        self.now = float(night.storm_start + 3600)
        extras = sorted((f for f in night.flights if f.kind == "extra"), key=lambda f: f.id)
        self.operable = {f.id for f in extras[: len(extras) // 2]}
        self.free = {f.id: list(f.free_seats) for f in night.flights if f.kind in ("scheduled", "partner")}
        self.free.update({f.id: seat_ids(f.aircraft) for f in extras if f.id in self.operable})
        self.sent: list[tuple[str, dict]] = []

    def chance(self, *keys: object) -> float:
        return chance(self.night.seed, "sandbox", *keys)

    def find_flights(self, dest: str) -> list[dict]:
        out = []
        for f in self.night.flights:
            if f.dest != dest or f.kind == "cancelled":
                continue
            info = {"id": f.id, "dep": f.dep, "airline": f.airline, "kind": f.kind}
            if f.kind == "extra" and f.id not in self.operable:
                out.append(option(info, 0, wait=True))
            else:
                out.append(option(info, len(self.free[f.id])))
        return out

    def book_seat(self, pax: str, option: dict) -> dict:
        if not option or option.get("flight") is None:
            return dict(NO_SEAT)
        if option.get("wait"):
            return {
                "status": "waiting",
                "booked": False,
                "flight": option["flight"],
                "seat": None,
                "dep": option["dep"],
            }
        free = self.free.get(option["flight"], [])
        if not free:
            return dict(NO_SEAT)
        return {
            "status": "booked",
            "booked": True,
            "flight": option["flight"],
            "seat": free.pop(0),
            "dep": option["dep"],
        }

    def _tell(self, agent: str, **values: Any) -> dict:
        self._need(**values)
        self.sent.append((agent, values))
        return {"sent": True}

    def messaging(self, pax, flight, seat, dep):
        return self._tell("messaging", pax=pax, flight=flight, seat=seat, dep=dep)

    def baggage(self, pax, flight):
        return self._tell("baggage", pax=pax, flight=flight)

    def hotels(self, pax, dep):
        return self._tell("hotels", pax=pax, dep=dep)

    def compensation(self, pax, delay_hours):
        return self._tell("compensation", pax=pax, delay_hours=delay_hours)


def _sample(night) -> list:
    """60 passengers of p1: everyone flying to Brazil comes first (the fare rules matter there)."""
    from ..night.places import GAROA

    people = sorted(night.passengers, key=lambda p: p.id)
    brazil = [p for p in people if p.dest in GAROA]
    picked = brazil[:: max(1, len(brazil) // 24)][:24]
    rest = [p for p in people if p not in picked]
    picked += rest[:: max(1, len(rest) // (SAMPLE - len(picked)))][: SAMPLE - len(picked)]
    return picked


def _who_wasnt_told(answer: dict, request: dict, sent: list[tuple[str, dict]]) -> list[str]:
    """Who this passenger's run should have told and didn't. A passenger waiting for an extra
    flight still needs a bed; one with a seat needs a text, vouchers, and their bags moved."""
    told = {agent for agent, _ in sent}
    booked = bool(answer.get("booked"))
    due = set()
    if booked:
        due |= {"messaging", "compensation"}
        if request.get("has_bags"):
            due.add("baggage")
    if request.get("needs_night") and answer.get("status") in ("booked", "waiting"):
        due.add("hotels")
    return sorted(due - told)


def _manifest_entry(night, p) -> dict:
    return {
        "id": p.id, "name": p.name, "dest": p.dest, "bags": p.bags, "local": p.local, "interline": p.interline,
        "tier": p.tier, "booked_dep": night.flight(p.flight).dep,
    }  # fmt: skip


# ---- what the checks know about plans and logs -----------------------------------------------------


def _source_ok(src: Any, earlier: set[str], declared: set[str]) -> str | None:
    if not isinstance(src, str):
        return _t(f"una fuente tiene que ser un texto, no {src!r}", f"a source must be a string, not {src!r}")
    root, _, field = src.partition(".")
    if root == "clock" and not field:
        return None
    if root == "request":
        return (
            None
            if field in declared
            else _t(
                f"{src}: el contrato no declara {field!r} en su entrada",
                f"{src}: the contract's input doesn't declare {field!r}",
            )
        )
    if root in earlier:
        return None
    return _t(f"{src}: no hay un paso anterior {root!r}", f"{src}: there's no earlier step {root!r}")


def plan_problems(plan: Any, declared: set[str]) -> list[str]:
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        return [
            _t("el plan tiene que ser un dict con una lista de steps", "the plan must be a dict with a list of steps")
        ]
    problems = []
    for key in ("task_id", "agent"):
        if not plan.get(key):
            problems.append(_t(f"al plan le falta {key}", f"the plan has no {key}"))
    if not isinstance(plan.get("request"), dict):
        problems.append(_t("al plan le falta el request", "the plan has no request"))
    earlier: set[str] = set()
    ids_by_run: dict[str, str] = {}
    for step in plan["steps"]:
        sid, run_by = step.get("id"), step.get("run_by")
        if not sid or sid in earlier:
            problems.append(_t(f"id repetido o vacío: {sid!r}", f"repeated or empty id: {sid!r}"))
        if run_by not in STEPS:
            problems.append(_t(f"{sid}: no existe el paso {run_by!r}", f"{sid}: there's no step {run_by!r}"))
        else:
            expected = set(STEPS[run_by][0])
            got = set(step.get("parameters") or {})
            if got != expected:
                problems.append(f"{sid} ({run_by}): {sorted(got)} ≠ {sorted(expected)}")
            ids_by_run.setdefault(run_by, sid)
        for name, spec in (step.get("parameters") or {}).items():
            if isinstance(spec, dict) and "from" in spec:
                if issue := _source_ok(spec["from"], earlier, declared):
                    problems.append(f"{sid}.{name}: {issue}")
        for dep in step.get("after", []):
            if dep not in earlier:
                problems.append(
                    _t(
                        f"{sid} espera a {dep!r}, que no viene antes",
                        f"{sid} waits for {dep!r}, which doesn't come earlier",
                    )
                )
        for cond in step.get("only_if", []):
            if issue := _source_ok(cond, earlier, declared):
                problems.append(f"{sid}.only_if: {issue}")
        earlier.add(sid)
    order = [ids_by_run.get(r) for r in ("tool:fare_rules", "model:choose", "tool:book_seat")]
    if None in order:
        problems.append(_t("faltan fare_rules, choose o book_seat", "fare_rules, choose or book_seat is missing"))
    else:
        steps = {s.get("id"): s for s in plan["steps"]}
        options = (steps[order[1]].get("parameters") or {}).get("options")
        if not (isinstance(options, dict) and options.get("from") == order[0]):
            problems.append(
                _t(
                    "las opciones de choose no salen del paso de las reglas de tarifa",
                    "choose's options don't come from the fare rules step",
                )
            )
    for run_by in TELLS:
        if run_by not in ids_by_run:
            problems.append(_t(f"nadie le avisa a {run_by.split(':')[1]}", f"nobody tells {run_by.split(':')[1]}"))
    return problems


def _value(ref: str, request: dict, results: dict) -> Any:
    root, _, field = ref.partition(".")
    if root == "request":
        return request.get(field)
    result = results.get(root)
    if field:
        return result.get(field) if isinstance(result, dict) else None
    return result


def run_problems(plan: dict, log: Any) -> list[str]:
    """The official reading of a run against its plan (the same rules your conforms() has)."""
    if not isinstance(log, list) or not all(isinstance(e, dict) for e in log):
        return [_t("el log tiene que ser una lista de dicts", "the log must be a list of dicts")]
    problems = []
    steps = {s["id"]: s for s in plan["steps"]}
    seen: dict[str, int] = {}
    failed = any(e.get("status") == "failed" for e in log)
    request, results = plan["request"], {}
    for i, e in enumerate(log):
        sid = e.get("step")
        if e.get("status") not in ("done", "skipped", "failed"):
            problems.append(_t(f"entrada {i}: status {e.get('status')!r}", f"entry {i}: status {e.get('status')!r}"))
        if sid not in steps:
            problems.append(
                _t(f"{sid!r} está en el log pero no en el plan", f"{sid!r} is in the log but not in the plan")
            )
            continue
        if sid in seen:
            problems.append(_t(f"{sid} aparece dos veces", f"{sid} appears twice"))
        seen[sid] = i
        step = steps[sid]
        if e.get("run_by") != step["run_by"]:
            problems.append(f"{sid}: run_by {e.get('run_by')!r} ≠ {step['run_by']!r}")
        for before in step.get("after", []):
            if before not in seen:
                problems.append(_t(f"{sid} corrió antes que {before}", f"{sid} ran before {before}"))
        should_run = all(_value(c, request, results) for c in step.get("only_if", []))
        if e.get("status") == "skipped":
            if should_run:
                problems.append(
                    _t(f"{sid} se saltó, pero su only_if se cumplía", f"{sid} was skipped, but its only_if held")
                )
            if not e.get("reason"):
                problems.append(_t(f"{sid} se saltó sin reason", f"{sid} was skipped with no reason"))
            continue
        if not should_run:
            problems.append(
                _t(f"{sid} corrió, pero su only_if no se cumplía", f"{sid} ran, but its only_if didn't hold")
            )
        logged = e.get("parameters")
        if not isinstance(logged, dict):
            problems.append(_t(f"{sid}: faltan los parameters en el log", f"{sid}: the log has no parameters"))
            continue
        for name, spec in step["parameters"].items():
            entry = logged.get(name)
            source = spec["from"] if isinstance(spec, dict) and "from" in spec else "literal"
            if not isinstance(entry, dict) or entry.get("from") != source:
                problems.append(
                    _t(f"{sid}.{name}: la fuente no es {source}", f"{sid}.{name}: the source isn't {source}")
                )
            elif source not in ("clock", "literal") and entry.get("value") != _value(source, request, results):
                problems.append(
                    _t(
                        f"{sid}.{name}: el valor no es el de {source}",
                        f"{sid}.{name}: the value isn't the one at {source}",
                    )
                )
            elif source == "literal" and entry.get("value") != spec:
                problems.append(
                    _t(f"{sid}.{name}: el valor no es el del plan", f"{sid}.{name}: the value isn't the plan's")
                )
        if e.get("status") == "done":
            if "result" not in e:
                problems.append(_t(f"{sid}: falta result", f"{sid}: no result"))
            results[sid] = e.get("result")
    if not failed:
        for sid in steps:
            if sid not in seen:
                problems.append(
                    _t(f"{sid} está en el plan pero no en el log", f"{sid} is in the plan but not in the log")
                )
    return problems


def planted(plan: dict, log: list[dict]) -> dict[str, list[dict]]:
    """Five runs that didn't follow the plan, made from one that did."""
    by_run = {e["run_by"]: i for i, e in enumerate(log)}
    out = {}
    skipped_rules = [e for e in log if e["run_by"] != "tool:fare_rules"]
    out[_t("se saltó las reglas de tarifa", "skipped the fare rules")] = skipped_rules
    twice = copy.deepcopy(log)
    twice.insert(by_run["tool:book_seat"] + 1, copy.deepcopy(log[by_run["tool:book_seat"]]))
    out[_t("reservó dos veces", "booked twice")] = twice
    early = copy.deepcopy(log)
    early.insert(by_run["model:choose"], early.pop(by_run["tool:book_seat"]))
    out[_t("reservó antes de elegir", "booked before choosing")] = early
    nowhere = copy.deepcopy(log)
    entry = nowhere[by_run["tool:book_seat"]]
    first = next((name for name in entry["parameters"] if name != "pax"), next(iter(entry["parameters"])))
    value = entry["parameters"][first]["value"]
    entry["parameters"][first]["value"] = {**value, "flight": "F999+1"} if isinstance(value, dict) else "F999+1"
    out[_t("un valor que no sale de ningún lado", "a value from nowhere")] = nowhere
    silent = copy.deepcopy(log)
    tell = silent[by_run["agent:messaging"]]
    tell.update({"status": "skipped", "reason": "no time"})
    tell.pop("parameters", None)
    tell.pop("result", None)
    out[_t("no le avisó al pasajero", "didn't tell the passenger")] = silent
    return out


# ---- the checks --------------------------------------------------------------------------------------


def run(module: ModuleType) -> list[Result]:
    r_contract = Result({"es": "El contrato", "en": "The contract"}, TYPES)
    r_alone = Result({"es": "Se llama solo con el contrato", "en": "Called from the contract alone"}, ENDPOINT)
    r_plan = Result({"es": "Un plan que un programa puede revisar", "en": "A plan a program can check"}, PLAN)
    r_log = Result({"es": "El log sigue al plan", "en": "The log follows the plan"}, SUBSTITUTION)
    r_conforms = Result({"es": "Tu verificador de conformidad", "en": "Your conformance checker"}, EXECUTION)
    r_night = Result({"es": "Una noche con tu agente", "en": "A night with your agent"}, CODE)
    results = [r_contract, r_alone, r_plan, r_log, r_conforms, r_night]

    def not_started(rs):
        for r in rs:
            r.started = r.passed = False
        return results

    try:
        contract = attempt(r_contract, module.contract)
    except NotStarted:
        return not_started(results)
    if not isinstance(contract, dict):
        return results
    missing = [k for k in KEYS if k not in contract]
    if missing:
        r_contract.fail(_t("faltan: ", "missing: ") + ", ".join(missing))
    if contract.get("type") not in TYPES_OF_AGENT:
        r_contract.fail(
            _t(
                f"type tiene que ser uno de {', '.join(TYPES_OF_AGENT)}",
                f"type must be one of {', '.join(TYPES_OF_AGENT)}",
            )
        )
    elif contract["type"] != "task-oriented":
        r_contract.fail(
            _t(
                "rebooking recibe un caso y devuelve un resultado: ¿qué tipo de agente es ese?",
                "rebooking gets a request and hands back a result: which type of agent is that?",
            )
        )
    if not isinstance(contract.get("limits"), list) or not contract.get("limits"):
        r_contract.fail(
            _t("limits tiene que ser una lista con al menos un límite", "limits must be a list with at least one limit")
        )
    schemas = {}
    for key in ("input", "output"):
        try:
            Draft202012Validator.check_schema(contract.get(key) or {})
            schemas[key] = Draft202012Validator(contract.get(key) or {})
        except SchemaError as e:
            r_contract.fail(f"{key}: {e.message}")
    if r_contract.passed:
        r_contract.score = f"{contract['name']} {contract['version']} · {contract['type']}"
    if len(schemas) < 2:
        return _rest_cannot_run(results)

    night = load(NIGHTS / "practice" / "p1.json")
    declared = set((contract["input"].get("properties") or {}).keys())
    tools = SandboxTools(night)
    good_logs: list[tuple[dict, list[dict]]] = []
    right = {"alone": 0, "plan": 0, "log": 0}
    sample = _sample(night)
    for p in sample:
        full = request_for(_manifest_entry(night, p))
        request = {k: v for k, v in full.items() if k in declared}
        errors = sorted(schemas["input"].iter_errors(request), key=str)
        if errors:
            r_alone.details.append(
                f"{p.id}: "
                + _t(
                    "la entrada del contrato rechaza lo que manda quien llama: ",
                    "the contract's input rejects the caller's request: ",
                )
                + errors[0].message
            )
            continue
        try:
            plan = module.plan(dict(request))
        except NotImplementedError:
            return not_started(results[1:])
        except KeyError as e:
            r_alone.details.append(
                _t(
                    f"{p.id}: tu plan lee {e}, que el contrato no declara",
                    f"{p.id}: your plan reads {e}, which the contract doesn't declare",
                )
            )
            continue
        except Exception as e:
            r_plan.details.append(f"{p.id}: plan() {type(e).__name__}: {e}")
            continue
        issues = plan_problems(plan, declared)
        if issues:
            r_plan.details.append(f"{p.id}: {issues[0]}")
            continue
        right["plan"] += 1
        told_before = len(tools.sent)
        try:
            log = module.execute(plan, tools)
        except NotImplementedError:
            for r in (r_log, r_conforms, r_night):
                r.started = r.passed = False
            r_alone.started = r_alone.passed = False
            tally(r_plan, right["plan"], len(sample), {"es": "planes", "en": "plans"})
            return results
        except Exception as e:
            r_log.details.append(f"{p.id}: execute() {type(e).__name__}: {e}")
            continue
        issues = run_problems(plan, log)
        if issues:
            r_log.details.append(f"{p.id}: {issues[0]}")
            continue
        right["log"] += 1
        answer = booking_result(log)
        errors = sorted(schemas["output"].iter_errors(answer), key=str) if answer is not None else []
        if answer is None:
            r_alone.details.append(
                _t(
                    f"{p.id}: no hay una respuesta (el paso book_seat no corrió)",
                    f"{p.id}: no answer (the book_seat step didn't run)",
                )
            )
        elif errors:
            r_alone.details.append(
                _t(
                    f"{p.id}: la salida del contrato rechaza la respuesta: ",
                    f"{p.id}: the contract's output rejects the answer: ",
                )
                + errors[0].message
            )
        elif answer.get("booked") and night.flight(answer["flight"]).dest != p.dest:
            r_alone.details.append(_t(f"{p.id}: reservado a otra ciudad", f"{p.id}: booked to another city"))
        elif answer.get("booked") and night.flight(answer["flight"]).airline == "garoa" and not p.interline:
            r_alone.details.append(
                _t(
                    f"{p.id}: un asiento del socio sin tarifa interlínea",
                    f"{p.id}: a partner's seat without an interline fare",
                )
            )
        elif missing := _who_wasnt_told(answer, full, tools.sent[told_before:]):
            r_alone.details.append(
                _t(
                    f"{p.id} ({answer.get('status')}): nadie le avisó a {', '.join(missing)}",
                    f"{p.id} ({answer.get('status')}): nobody told {', '.join(missing)}",
                )
            )
        else:
            right["alone"] += 1
            good_logs.append((plan, log))
    tally(r_alone, right["alone"], len(sample), {"es": "pasajeros", "en": "passengers"})
    tally(r_plan, right["plan"], len(sample), {"es": "planes", "en": "plans"})
    tally(r_log, right["log"], len(sample), {"es": "ejecuciones", "en": "runs"})

    # the conformance checker: a clean run, then five that went off the plan
    full_runs = [
        (pl, lg)
        for pl, lg in good_logs
        if {e["run_by"] for e in lg if e["status"] == "done"}
        >= {"tool:fare_rules", "tool:book_seat", "agent:messaging"}
    ]
    full_runs = full_runs[:: max(1, len(full_runs) // 3)][:3]
    if not full_runs:
        r_conforms.started = r_conforms.passed = False
        r_conforms.notes.append(
            _t(
                "Hace falta una ejecución con reserva que siga su plan.",
                "It needs a run with a booking that follows its plan.",
            )
        )
    else:
        cases = {}
        for i, (plan, log) in enumerate(full_runs, 1):
            pax = plan.get("request", {}).get("pax", i)
            cases[f"{pax}: " + _t("una ejecución que siguió el plan", "a run that followed the plan")] = (
                plan,
                log,
                False,
            )
            cases.update({f"{pax}: {name}": (plan, bad, True) for name, bad in planted(plan, log).items()})
        ok = 0
        for name, (plan, lg, should_flag) in cases.items():
            try:
                found = attempt(r_conforms, module.conforms, plan, copy.deepcopy(lg))
            except NotStarted:
                r_conforms.started = r_conforms.passed = False
                break
            if found is None:
                continue
            if bool(found) == should_flag:
                ok += 1
            elif should_flag:
                r_conforms.details.append(_t(f"no marcó: {name}", f"didn't flag: {name}"))
            else:
                r_conforms.details.append(_t(f"marcó {name}: {found[0]}", f"flagged {name}: {found[0]}"))
        else:
            tally(r_conforms, ok, len(cases), {"es": "casos", "en": "cases"})

    # a whole night
    engine = Engine(night, build("naive"), agents={"rebooking": planned_rebooking(module)}).run()
    board = score(engine)
    agent = engine.runtimes["rebooking"].agent
    invalid = [
        o
        for o in board.outcomes
        if o.seat in SEAT_PROBLEMS
        and engine.world.bookings.get(o.pax)
        and engine.world.bookings[o.pax].by == "rebooking"
    ]
    crashes = [line for line in engine.agent_logs.get("rebooking", []) if "ERROR" in line or "stopped" in line]
    off_plan = [(pl, lg) for _, pl, lg in agent.runs if run_problems(pl, lg)]
    failed = [(pl, lg) for _, pl, lg in agent.runs if any(e.get("status") == "failed" for e in lg)]
    today = score(Engine(night, build("naive")).run())
    if failed:
        step = next(e for e in failed[0][1] if e.get("status") == "failed")
        r_night.fail(
            _t(f"{len(failed)} ejecuciones terminaron en un paso fallido; por ejemplo {step['step']}: {step.get('error')}",
               f"{len(failed)} runs ended in a failed step; e.g. {step['step']}: {step.get('error')}")
        )  # fmt: skip
    if board.rehoused < today.rehoused:
        r_night.fail(
            _t(f"la noche quedó peor que hoy: {board.rehoused} reubicados, contra {today.rehoused} con el agente de siempre",
               f"the night is worse than today's: {board.rehoused} rehoused, against {today.rehoused} with the old agent")
        )  # fmt: skip
    if invalid:
        r_night.fail(
            _t(
                f"{len(invalid)} reservas no válidas (por ejemplo {invalid[0].pax}: {invalid[0].seat})",
                f"{len(invalid)} invalid bookings (e.g. {invalid[0].pax}: {invalid[0].seat})",
            )
        )
    if crashes:
        r_night.fail(
            _t(
                f"{len(crashes)} errores en el agente: {crashes[0]}",
                f"{len(crashes)} errors in the agent: {crashes[0]}",
            )
        )
    if off_plan:
        r_night.fail(
            _t(
                f"{len(off_plan)} ejecuciones no siguieron su plan: ",
                f"{len(off_plan)} runs didn't follow their plan: ",
            )
            + run_problems(*off_plan[0])[0]
        )
    if not agent.runs:
        r_night.fail(_t("el agente no ejecutó ningún plan", "the agent ran no plan"))
    if r_night.passed:
        r_night.score = _t(
            f"0 reservas no válidas · {len(agent.runs)} planes", f"0 invalid bookings · {len(agent.runs)} plans"
        )
    return results


def _rest_cannot_run(results: list[Result]) -> list[Result]:
    for r in results[1:]:
        r.passed = False
        r.started = True
        r.details.append(
            _t("necesita un contrato con input y output válidos", "needs a contract with a valid input and output")
        )
    return results
