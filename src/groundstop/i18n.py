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
    "board.logs": {"es": "Registros en {path}", "en": "Logs in {path}"},
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
    "cli.help.mesh": {
        "es": "naive (la de Fragata hoy) o un módulo cuyo build() devuelve tu malla",
        "en": "naive (Fragata's today) or a module whose build() returns your mesh",
    },
    "cli.help.out": {
        "es": "carpeta para los registros (por defecto runs/<noche>/)",
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
    "mesh.naive": {"es": "ingenua", "en": "naive"},
    "pack.practice": {"es": "práctica", "en": "practice"},
    "pack.standard": {"es": "estándar", "en": "standard"},
    "pack.final": {"es": "final", "en": "final"},
}
