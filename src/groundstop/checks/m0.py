"""Checks for milestone 0, the storm: you replayed night p1 and read what went wrong.

The check replays p1 with the naive mesh itself (the night is deterministic, so it's the same
night you saw) and compares your answers with what really happened.
"""

from __future__ import annotations

import json
from types import ModuleType

from .. import NIGHTS, RUNS
from ..mesh import build
from ..milestones import Lesson
from ..night.model import load
from ..score import score
from ..sim.engine import Engine
from .core import NotStarted, Result, attempt

GAPS = Lesson(
    "what-is-an-agentic-mesh",
    {
        "es": ("Un asistente se convirtió en decenas de agentes", "un-asistente-se-convirtió-en-decenas-de-agentes"),
        "en": ("One assistant became dozens of agents", "one-assistant-became-dozens-of-agents"),
    },
)
NIGHT = "p1"


def truth():
    engine = Engine(load(NIGHTS / "practice" / f"{NIGHT}.json"), build("naive")).run()
    board = score(engine)
    doubles = {key: sorted(p for _, p in holders) for key, holders in engine.world.holders.items() if len(holders) > 1}
    never = {
        t.msg.body["flight"]
        for t in engine.traffic
        if t.status == "LOST" and t.msg.to == "crew" and t.msg.kind == "staff_flight"
    }
    return board, doubles, never


def run(module: ModuleType) -> list[Result]:
    ran = Result({"es": "Reprodujiste la noche p1", "en": "You replayed night p1"}, None)
    rehoused = Result({"es": "Leíste el marcador", "en": "You read the scoreboard"}, GAPS)
    seat = Result({"es": "Un asiento vendido dos veces", "en": "A seat sold twice"}, GAPS)
    crew = Result({"es": "El mensaje que crew nunca recibió", "en": "The message crew never got"}, GAPS)
    results = [ran, rehoused, seat, crew]

    board_file = RUNS / NIGHT / "scoreboard.json"
    if board_file.exists() and json.loads(board_file.read_text(encoding="utf-8")).get("mesh") == "naive":
        ran.score = "runs/p1/"
    else:
        ran.fail(
            {
                "es": "No está runs/p1/scoreboard.json de la malla ingenua.",
                "en": "runs/p1/scoreboard.json from the naive mesh isn't there.",
            }[_lang()]
        )
        ran.notes.append(
            {
                "es": "Ejecuta `uv run ground-stop replay` (o `docker compose up`).",
                "en": "Run `uv run ground-stop replay` (or `docker compose up`).",
            }[_lang()]
        )

    try:
        answers = attempt(rehoused, module.answers)
    except NotStarted:
        for r in results[1:]:
            r.started = r.passed = False
        return results
    if not isinstance(answers, dict):
        for r in results[1:]:
            r.fail("answers() " + {"es": "tiene que devolver un dict", "en": "must return a dict"}[_lang()])
        return results

    board, doubles, never = truth()

    got = answers.get("rehoused")
    if got == board.rehoused:
        rehoused.score = f"{got} / {board.total}"
    else:
        rehoused.fail(
            {
                "es": f"rehoused: {got!r} no es lo que dice la primera línea del marcador",
                "en": f"rehoused: {got!r} isn't what the scoreboard's first line says",
            }[_lang()]
        )

    s = answers.get("seat_sold_twice") or {}
    key = (s.get("flight"), s.get("seat"))
    if key not in doubles:
        seat.fail(
            {
                "es": f"{key[0]} {key[1]}: a las 06:00 ese asiento no tiene dos pasajeros (passengers.jsonl los marca seat_taken)",
                "en": f"{key[0]} {key[1]}: at 06:00 that seat doesn't have two passengers (passengers.jsonl marks them seat_taken)",
            }[_lang()]
        )
    elif len(set(s.get("passengers") or [])) != 2 or not set(s["passengers"]) <= set(doubles[key]):
        seat.fail(
            {
                "es": f"{key[0]} {key[1]} sí, pero esos no son dos de los pasajeros que lo tienen a las 06:00",
                "en": f"{key[0]} {key[1]} is right, but those aren't two of the passengers who hold it at 06:00",
            }[_lang()]
        )
    else:
        seat.score = f"{key[0]} {key[1]}"

    flight = answers.get("never_reached_crew")
    if flight in never:
        crew.score = str(flight)
    else:
        crew.fail(
            {
                "es": f"{flight!r}: el mensaje que pedía tripulación para ese vuelo sí llegó (busca LOST en traffic.log)",
                "en": f"{flight!r}: the crew request for that flight did arrive (look for LOST in traffic.log)",
            }[_lang()]
        )
    return results


def _lang() -> str:
    from ..i18n import lang

    return lang()
