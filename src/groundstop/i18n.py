"""Spanish first, English second: every text a person reads goes through `t()`.

The language comes from `--lang`, else the GROUND_STOP_LANG environment variable, else Spanish.
Code, command names, JSON keys and log lines stay in English.
"""

from __future__ import annotations

import os

LANGS = ("es", "en")
_lang = os.environ.get("GROUND_STOP_LANG", "es") if os.environ.get("GROUND_STOP_LANG") in LANGS else "es"


def set_lang(lang: str) -> None:
    global _lang
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {LANGS}")
    _lang = lang


def lang() -> str:
    return _lang


def num(n: float) -> str:
    """1234567 → 1.234.567 in Spanish, 1,234,567 in English."""
    text = f"{round(n):,}"
    return text.replace(",", ".") if _lang == "es" else text


def t(key: str, **kw: object) -> str:
    entry = TEXT[key]
    return entry[_lang].format(**kw)


TEXT: dict[str, dict[str, str]] = {
    # scoreboard
    "board.title": {
        "es": "Todos en tierra · noche {night} ({pack}) · malla: {mesh}",
        "en": "Ground Stop · night {night} ({pack}) · mesh: {mesh}",
    },
    "board.storm": {
        "es": "Tormenta a las {start}: {flights} vuelos cancelados, {pax} pasajeros varados en Tocumen",
        "en": "Storm at {start}: {flights} flights cancelled, {pax} passengers stranded at Tocumen",
    },
    "board.rehoused": {"es": "Reubicados a las 06:00", "en": "Rehoused by 06:00"},
    "board.no_care": {"es": "Durmieron en el aeropuerto sin atención", "en": "Slept at the airport without care"},
    "board.no_seat": {"es": "Sin asiento válido", "en": "Without a valid seat"},
    "board.not_told": {"es": "Sin un mensaje con su vuelo final", "en": "Never told their final flight"},
    "board.double_seats": {"es": "Asientos vendidos dos veces", "en": "Seats sold twice"},
    "board.lost": {"es": "Mensajes perdidos", "en": "Messages lost"},
    "board.unreachable": {
        "es": "Enviados a un hotel al que no pueden llegar",
        "en": "Sent to a hotel they can't reach",
    },
    "board.double_rooms": {"es": "Habitaciones reservadas dos veces", "en": "Rooms booked twice"},
    "board.fake_rooms": {"es": "Habitaciones en un hotel que no existe", "en": "Rooms at a hotel that doesn't exist"},
    "board.invalid": {"es": "Reservas no válidas", "en": "Invalid bookings"},
    "board.vouchers": {"es": "Vouchers por encima de lo que corresponde", "en": "Vouchers over entitlement"},
    "board.unauthorized": {"es": "Acciones no autorizadas", "en": "Unauthorized actions"},
    "board.denied": {"es": "Llamadas rechazadas por la malla", "en": "Calls the mesh denied"},
    "board.bags": {"es": "Maletas sin reasignar", "en": "Bags not re-tagged"},
    "board.errors": {"es": "Errores dentro de los agentes", "en": "Errors inside agents"},
    "board.messages": {"es": "Mensajes entre agentes", "en": "Messages between agents"},
    "board.logs": {"es": "Logs en {path}", "en": "Logs in {path}"},
    "board.usd": {"es": "{count} (USD {amount})", "en": "{count} (USD {amount})"},
    # cli
    "cli.no_night": {
        "es": "No hay ninguna noche {night!r}. Prueba `ground-stop nights`.",
        "en": "No night {night!r}. Try `ground-stop nights`.",
    },
    "cli.nights.header": {
        "es": "Noche  Paquete    Tormenta  Vuelos  Pasajeros",
        "en": "Night  Pack       Storm     Flights Passengers",
    },
    "cli.replaying": {
        "es": "Reproduciendo la noche {night} con la malla {mesh}…",
        "en": "Replaying night {night} with the {mesh} mesh…",
    },
    "cli.generated": {"es": "Generadas {count} noches en {path}", "en": "Generated {count} nights in {path}"},
    "cli.description": {
        "es": "Todos en tierra: reproduce una noche de tormenta con una malla de agentes y lee el marcador.",
        "en": "Ground Stop: replay a storm night through an agent mesh and read the scoreboard.",
    },
    "cli.lang": {"es": "idioma de lo que se muestra (es, en)", "en": "language of what is shown (es, en)"},
    "cli.help.nights": {"es": "las noches de este repositorio", "en": "the nights in this repo"},
    "cli.help.show": {"es": "qué pasa en una noche", "en": "what happens on a night"},
    "cli.help.replay": {
        "es": "reproduce una noche y muestra el marcador",
        "en": "replay a night and show the scoreboard",
    },
    "cli.help.rebooking": {
        "es": "mine (tu agente de reprogramación del hito 2) o un módulo con plan() y execute()",
        "en": "mine (your rebooking agent from milestone 2) or a module with plan() and execute()",
    },
    "cli.help.mesh": {
        "es": "naive (la de Fragata hoy), mine (src/groundstop/mine/mesh.py) o un módulo cuyo build() devuelve una malla",
        "en": "naive (Fragata's today), mine (src/groundstop/mine/mesh.py) or a module whose build() returns a mesh",
    },
    "cli.help.entry_rules": {
        "es": "mine (tu agente de reglas de entrada del hito 7) o un módulo con entry_rules()",
        "en": "mine (your entry-rules agent from milestone 7) or a module with entry_rules()",
    },
    "cli.help.out": {
        "es": "carpeta para los logs (por defecto runs/<noche>/)",
        "en": "folder for the logs (default runs/<night>/)",
    },
    "cli.help.generate": {
        "es": "vuelve a generar un paquete de noches desde sus semillas",
        "en": "rebuild a pack of nights from its seeds",
    },
    # show
    "show.title": {
        "es": "Noche {night} ({pack}) · la tormenta llega a las {start}",
        "en": "Night {night} ({pack}) · the storm hits at {start}",
    },
    "show.flights": {"es": "Salidas de esta noche, todas canceladas:", "en": "Tonight's departures, all cancelled:"},
    "show.pax": {"es": "{pax} pasajeros", "en": "{pax} passengers"},
    "show.cancel_at": {"es": "se cancela a las {at}", "en": "cancelled at {at}"},
    "show.extras": {
        "es": "Vuelos extra para mañana: {count} (necesitan tripulación; hay {crews} de reserva)",
        "en": "Extra flights for tomorrow: {count} (they need crews; {crews} on reserve)",
    },
    "show.hotels": {
        "es": "Habitaciones en Hoteles Ondelia: {rooms} · lugares en la sala de pernocta del aeropuerto: {care}",
        "en": "Rooms at Hoteles Ondelia: {rooms} · places in the airport's overnight lounge: {care}",
    },
    "show.events": {
        "es": "Lo que va a pasar (en las noches de práctica se avisa):",
        "en": "What will happen (practice nights tell you):",
    },
    "show.hidden": {
        "es": "Lo que pasa esta noche no se avisa: para eso están las noches de práctica.",
        "en": "What happens tonight isn't announced: that's what the practice nights are for.",
    },
    "event.ground_stop": {
        "es": "Una tormenta cierra el aeropuerto. Operaciones empieza a cancelar las salidas, en tandas.",
        "en": "A storm closes the airport. Operations starts cancelling departures, in waves.",
    },
    "event.partner_moves": {
        "es": "{agent} pasa a una versión nueva en otra dirección ({to}); la anterior deja de responder.",
        "en": "{agent} moves to a new version at another address ({to}); the old one stops answering.",
    },
    "event.crash": {
        "es": "El agente {agent} se cae y vuelve a arrancar {minutes} minutos después, sin lo que tenía en memoria.",
        "en": "The {agent} agent crashes and restarts {minutes} minutes later, with nothing it kept in memory.",
    },
    "event.intruder": {
        "es": "Aparece {agent} ({address}) ofreciendo habitaciones a USD {price} a quien las pida.",
        "en": "{agent} ({address}) shows up offering rooms at USD {price} to anyone who asks.",
    },
    "event.injection": {
        "es": "El pasajero {pax} responde un SMS con una instrucción escondida para el agente de compensaciones.",
        "en": "Passenger {pax} answers a text with an instruction hidden for the compensation agent.",
    },
    # checks
    "check.title": {"es": "Hito {id} · {title}", "en": "Milestone {id} · {title}"},
    "check.instructions": {"es": "Instrucciones: {url}", "en": "Instructions: {url}"},
    "check.not_started": {"es": "sin empezar", "en": "not started"},
    "check.more": {"es": "… y {n} más", "en": "… and {n} more"},
    "check.read": {"es": "Lee: {title} → {url}", "en": "Read: {title} → {url}"},
    "check.summary": {"es": "{passed}/{total} comprobaciones pasan", "en": "{passed}/{total} checks pass"},
    "check.done": {
        "es": "Hito completo. Márcalo como hecho en el sitio y sigue con el próximo.",
        "en": "Milestone complete. Mark it done on the site and move on to the next one.",
    },
    "check.raised": {"es": "{fn} lanzó una excepción: {error}", "en": "{fn} raised: {error}"},
    "check.none": {"es": "{fn} devolvió None: ¿falta un return?", "en": "{fn} returned None: did it forget a return?"},
    "check.running": {"es": "Ejecutando el hito {id} sobre {what}…", "en": "Running milestone {id} on {what}…"},
    "check.reference": {"es": "la solución de referencia", "en": "the reference solution"},
    "cli.no_milestone": {"es": "No hay un hito {id!r}. Hay: {ids}", "en": "No milestone {id!r}. Available: {ids}"},
    "cli.help.trace": {
        "es": "la traza de un pasajero, con el tracer de tu malla",
        "en": "one passenger's trace, through your mesh's tracer",
    },
    "cli.no_tracer": {
        "es": "Tu malla todavía no tiene un tracer (hito 4).",
        "en": "Your mesh has no tracer yet (milestone 4).",
    },
    "cli.no_trace": {
        "es": "No hay ninguna traza de {pax} en la noche {night}.",
        "en": "There's no trace for {pax} on night {night}.",
    },
    "cli.trace_title": {"es": "{pax}, noche {night} · traza {trace}", "en": "{pax}, night {night} · trace {trace}"},
    "cli.trace_slowest": {
        "es": "El salto más lento: {agent}, {minutes} min",
        "en": "The slowest hop: {agent}, {minutes} min",
    },
    "cli.help.check": {"es": "ejecuta las comprobaciones de un hito", "en": "run a milestone's checks"},
    "cli.help.reference": {
        "es": "comprueba la solución de referencia en vez de tu código",
        "en": "check the reference solution instead of your code",
    },
    "cli.help.use_reference": {
        "es": "cambia tu archivo por la solución de referencia",
        "en": "swap your file for the reference solution",
    },
    "cli.help.undo": {"es": "vuelve a poner tu archivo", "en": "put your own file back"},
    "cli.backup_exists": {
        "es": "{path} ya existe: ejecuta antes con --undo, o bórralo",
        "en": "{path} already exists: run with --undo first, or remove it",
    },
    "cli.no_backup": {"es": "No hay copia en {path}", "en": "No backup at {path}"},
    "cli.restored": {"es": "Volvió tu archivo del hito {id}.", "en": "Restored your file for milestone {id}."},
    "cli.replaced": {
        "es": "{path} ahora es la referencia; el tuyo quedó como *.mine.py (--undo lo devuelve).",
        "en": "{path} is now the reference; yours is kept as *.mine.py (--undo puts it back).",
    },
    "mesh.naive": {"es": "ingenua", "en": "naive"},
    "mesh.mine": {"es": "la tuya", "en": "yours"},
    "pack.practice": {"es": "práctica", "en": "practice"},
    "pack.standard": {"es": "estándar", "en": "standard"},
    "pack.final": {"es": "final", "en": "final"},
}
