"""Checks for milestone 1, count the agents.

The check replays two practice nights with the naive mesh into a temporary folder, runs your
functions on their logs, and compares them with what the simulation knows.
"""

from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType

from .. import COMPANY, NIGHTS
from ..company import load_company
from ..i18n import lang
from ..mesh import build
from ..milestones import Lesson
from ..night.model import load
from ..sim.engine import Engine
from .core import NotStarted, Result, attempt, tally

ECOSYSTEM = Lesson(
    "what-is-an-agentic-mesh",
    {
        "es": ("De un agente a un ecosistema", "de-un-agente-a-un-ecosistema"),
        "en": ("From one agent to an ecosystem", "from-one-agent-to-an-ecosystem"),
    },
)
GAPS = Lesson(
    "what-is-an-agentic-mesh",
    {
        "es": ("Un asistente se convirtió en decenas de agentes", "un-asistente-se-convirtió-en-decenas-de-agentes"),
        "en": ("One assistant became dozens of agents", "one-assistant-became-dozens-of-agents"),
    },
)
ONE_PLACE = Lesson(
    "what-is-an-agentic-mesh",
    {
        "es": ("La malla agéntica: un solo lugar donde conectarse", "la-malla-agéntica-un-solo-lugar-donde-conectarse"),
        "en": ("The agentic mesh: one place to plug in", "the-agentic-mesh-one-place-to-plug-in"),
    },
)
NIGHTS_CHECKED = ("p1", "p3")
CHANGES = (
    "reservations.cancel", "reservations.assign", "reservations.record_partner", "crews.assign", "sms.send",
    "vouchers.issue", "care.reserve", "stays.record", "bags.retag",
)  # fmt: skip
NIGHTS_UNIT = {"es": "noches", "en": "nights"}


def _is_address(name: str) -> bool:
    return name.startswith(("http://", "https://"))


def truth(engine: Engine) -> dict:
    company = load_company()
    gateways = set(company.gateways)
    declared = {a.id: ("partner" if a.outside else a.team) for a in company.agents.values()}
    names = set()
    pairs = set()
    for t in engine.traffic:
        sender, to = t.msg.sender, t.msg.to
        if sender not in gateways:
            names.add(sender)
        if not _is_address(to) and to not in gateways:
            names.add(to)
            if sender not in gateways and sender != to:
                pairs.add(frozenset((sender, to)))
    callers = {c.caller for c in engine.world.calls}
    unlisted = {n: ("inside" if n in callers else "outside") for n in names - set(declared)}
    by_op = defaultdict(set)
    for c in engine.world.calls:
        if c.target in CHANGES and c.status == "ok":
            by_op[c.target].add(c.caller)
    overlaps = {op: agents for op, agents in by_op.items() if len(agents) > 1}
    return {"declared": declared, "seen": names, "unlisted": unlisted, "overlaps": overlaps, "links": len(pairs)}


def _show(value) -> str:
    if isinstance(value, set | frozenset):
        return "{" + ", ".join(sorted(map(str, value))) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_show(v)}" for k, v in sorted(value.items())) + "}"
    return repr(value)


def _diff(got, want) -> str:
    if isinstance(got, dict) and isinstance(want, dict):
        missing = sorted(set(want) - set(got))
        extra = sorted(set(got) - set(want))
        wrong = sorted(k for k in set(got) & set(want) if _norm(got[k]) != _norm(want[k]))
        parts = []
        if missing:
            parts.append({"es": "faltan ", "en": "missing "}[lang()] + ", ".join(missing))
        if extra:
            parts.append({"es": "sobran ", "en": "extra "}[lang()] + ", ".join(extra))
        for k in wrong[:3]:
            parts.append(f"{k}: {_show(got[k])} ≠ {_show(want[k])}")
        return "; ".join(parts)
    if isinstance(got, set | frozenset | list) and isinstance(want, set):
        got = set(got)
        parts = []
        if want - got:
            parts.append({"es": "faltan ", "en": "missing "}[lang()] + ", ".join(sorted(want - got)))
        if got - want:
            parts.append({"es": "sobran ", "en": "extra "}[lang()] + ", ".join(sorted(map(str, got - want))))
        return "; ".join(parts)
    return f"{got!r} ≠ {want!r}"


def _norm(v):
    if isinstance(v, set | frozenset | list | tuple):
        return frozenset(v)
    return v


def run(module: ModuleType) -> list[Result]:
    declared = Result({"es": "Lo que declaran las configs", "en": "What the configs declare"}, GAPS)
    seen = Result({"es": "Lo que se ve en el tráfico", "en": "What the traffic shows"}, GAPS)
    unlisted = Result({"es": "Los agentes que nadie listó", "en": "The agents nobody listed"}, GAPS)
    overlaps = Result({"es": "Trabajos que hacen dos agentes", "en": "Jobs two agents do"}, ECOSYSTEM)
    links = Result({"es": "Pares que hablan directo", "en": "Pairs that talk directly"}, ONE_PLACE)
    results = [declared, seen, unlisted, overlaps, links]

    with tempfile.TemporaryDirectory() as tmp:
        runs = []
        for nid in NIGHTS_CHECKED:
            engine = Engine(load(NIGHTS / "practice" / f"{nid}.json"), build("naive")).run()
            out = Path(tmp) / nid
            engine.write_logs(out)
            runs.append((nid, out, truth(engine)))

        def judge(result: Result, call, key: str) -> None:
            right = 0
            for nid, out, want in runs:
                try:
                    got = attempt(result, call, out)
                except NotStarted:
                    raise
                if got is None:
                    continue
                if _norm_deep(got) == _norm_deep(want[key]):
                    right += 1
                else:
                    result.details.append(f"{nid}: {_diff(got, want[key])}")
            tally(result, right, len(runs), NIGHTS_UNIT)

        for result, call, key in [
            (declared, lambda out: module.declared(COMPANY), "declared"),
            (seen, lambda out: module.seen(out / "traffic.log"), "seen"),
            (unlisted, lambda out: module.unlisted(COMPANY, out / "traffic.log", out / "systems.log"), "unlisted"),
            (overlaps, lambda out: module.overlaps(out / "systems.log"), "overlaps"),
            (links, lambda out: module.links(out / "traffic.log"), "links"),
        ]:
            try:
                judge(result, call, key)
            except NotStarted:
                result.started = result.passed = False
    return results


def _norm_deep(v):
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return _norm(v)
