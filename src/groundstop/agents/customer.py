"""Customer team: rebooking, messages to passengers, compensation."""

from __future__ import annotations

import re
from collections import defaultdict

from ..mesh import Message
from ..sdk import Agent, Ctx, Denied
from ..sim.world import city, when
from ..util import at

PARTNER_DESTS = ("GRU", "GIG", "BSB")  # where Garoa flies from Tocumen
GIVE_UP = at(1, 4, 0)  # after this, stop waiting for extra flights and use the day after
SEAT_MAP_TTL = 900

# Cities a model mixes up when it's in a hurry: same country or same region, often the same customers.
NEAR = [
    ("GRU", "GIG", "BSB", "POA", "CNF", "MAO"), ("BOG", "MDE", "CLO", "CTG"), ("UIO", "GYE", "LIM", "VVI"),
    ("SCL", "EZE", "MVD", "ASU"), ("MEX", "CUN", "GDL"), ("MIA", "MCO", "JFK", "IAD", "LAX", "YYZ"),
    ("SJO", "SAL", "GUA", "MGA", "SAP"), ("HAV", "SDQ", "PUJ", "SJU"),
]  # fmt: skip

# How often the one-call-does-everything model slips (simulated; milestone 2 measures and fixes it)
SLIPS = {"wrong_city": 0.02, "skip_fare_rules": 0.3, "skip_bags": 0.03}


class Rebooking(Agent):
    """Finds every passenger of a cancelled flight a new flight, books it and tells everyone.

    One model call per passenger does it all: read the case, choose a flight, check the fare rules,
    book the seat, then tell messaging, baggage, hotels and compensation. It works most of the time.
    """

    id = "rebooking"
    servers = 4
    service = {"rebook": 6.0}
    default_service = 0.3

    def __init__(self) -> None:
        self.planned: dict[str, list[dict]] = defaultdict(list)  # extra flights by city, crew not confirmed
        self.operable: set[str] = set()
        self.offers: dict[str, list[dict]] = {}
        self.asked_partner: set[str] = set()
        self.waiting: dict[str, list[dict]] = defaultdict(list)
        self.views: dict[str, tuple[float, list[str]]] = {}
        self.taken: set[tuple[str, str]] = set()
        self.night_sent: set[str] = set()
        self.at_partner: dict[str, dict] = {}

    def on_start(self, ctx: Ctx) -> None:
        ctx.later(GIVE_UP - ctx.now, "give_up")

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "flight_cancelled":
            for p in ctx.call("reservations", "manifest", flight=b["flight"]):
                ctx.work("rebook", {"pax": p})
                if p["dest"] in PARTNER_DESTS and p["dest"] not in self.asked_partner:
                    self.asked_partner.add(p["dest"])
                    ctx.send("garoa-seats", "seat_request", {"dest": p["dest"]})
        elif msg.kind == "extras_planned":
            for f in b["flights"]:
                self.planned[f["dest"]].append(f)
        elif msg.kind == "seat_offer":
            self.offers[b["dest"]] = [dict(o) for o in b["flights"]]
            for p in self.waiting.pop(b["dest"], []):
                ctx.work("rebook", {"pax": p})
        elif msg.kind == "flight_operable":
            self.operable.add(b["flight"])
            for dest, flights in self.planned.items():
                if any(f["id"] == b["flight"] for f in flights):
                    for p in self.waiting.pop(dest, []):
                        ctx.work("rebook", {"pax": p})
        elif msg.kind == "flight_not_operable":
            for flights in self.planned.values():
                flights[:] = [f for f in flights if f["id"] != b["flight"]]
        elif msg.kind == "booked":
            p = self.at_partner.pop(b["pax"], None)
            if p:
                ctx.call("reservations", "record_partner", pax=p["id"], flight=b["flight"], seat=b["seat"])
                self.after_booking(p, b["flight"], b["seat"], b["dep"], ctx)
        elif msg.kind == "sold_out":
            p = self.at_partner.pop(b["pax"], None)
            for o in self.offers.get(p["dest"] if p else "", []):
                if o["flight"] == b["flight"]:
                    o["free"] = 0
            if p:
                ctx.work("rebook", {"pax": p, "no_partner": True})
        elif msg.kind == "rebook":
            self.rebook(b["pax"], ctx, final=b.get("final", False), no_partner=b.get("no_partner", False))
        elif msg.kind == "give_up":
            for dest in list(self.waiting):
                for p in self.waiting.pop(dest):
                    ctx.work("rebook", {"pax": p, "final": True})

    def slips(self, p: dict, ctx: Ctx) -> set[str]:
        return {name for name, rate in SLIPS.items() if ctx.chance("rebooking", p["id"], name) < rate}

    def rebook(self, p: dict, ctx: Ctx, final: bool, no_partner: bool) -> None:
        if not ctx.claim(f"case/{p['id']}"):
            return
        slips = self.slips(p, ctx)
        dest = p["dest"]
        if "wrong_city" in slips:
            near = next((group for group in NEAR if dest in group), ())
            dest = next((c for c in near if c != dest and ctx.call("reservations", "flights_to", dest=c)), dest)
        flights = ctx.call("reservations", "flights_to", dest=dest)
        tomorrow = [f for f in flights if f["kind"] == "scheduled" and f["dep"] < at(2, 0)]
        extras = [f for f in flights if f["kind"] == "extra"]
        later = [f for f in flights if f["kind"] == "scheduled" and f["dep"] >= at(2, 0)]

        for f in tomorrow + [e for e in extras if e["id"] in self.operable]:
            seat = self.take_seat(f["id"], ctx)
            if seat:
                return self.book(p, f, seat, ctx)

        if not no_partner and dest in PARTNER_DESTS and (p["interline"] or "skip_fare_rules" in slips):
            for o in self.offers.get(dest, []):
                if o["free"] > 0:
                    o["free"] -= 1
                    self.at_partner[p["id"]] = p
                    ctx.send("garoa-seats", "book", {"pax": p["id"], "name": p["name"], "flight": o["flight"]})
                    self.night_for(p, o["dep"], ctx)
                    return

        coming = [e for e in self.planned.get(dest, []) if e["id"] not in self.operable]
        if coming and not final:
            self.waiting[dest].append(p)
            self.night_for(p, min(e["dep"] for e in coming), ctx)
            return

        for f in later:
            seat = self.take_seat(f["id"], ctx)
            if seat:
                return self.book(p, f, seat, ctx)
        if final:
            ctx.log(f"no seat to {dest} for {p['id']}")
        else:
            self.waiting[dest].append(p)  # try again when a partner offer or an extra flight comes in

    def take_seat(self, flight: str, ctx: Ctx) -> str | None:
        seen, free = self.views.get(flight, (float("-inf"), []))
        if ctx.now - seen >= SEAT_MAP_TTL:
            free = ctx.call("reservations", "seat_map", flight=flight)
            self.views[flight] = (ctx.now, free)
        for seat in free:
            if (flight, seat) in self.taken:
                continue
            self.taken.add((flight, seat))
            if ctx.claim(f"seat/{flight}/{seat}"):
                return seat
        return None

    def book(self, p: dict, f: dict, seat: str, ctx: Ctx) -> None:
        ctx.call("reservations", "assign", flight=f["id"], seat=seat, pax=p["id"])
        self.after_booking(p, f["id"], seat, f["dep"], ctx)

    def after_booking(self, p: dict, flight: str, seat: str, dep: float, ctx: Ctx) -> None:
        ctx.send("messaging", "notify", {"pax": p["id"], "flight": flight, "seat": seat, "dep": dep})
        if p["bags"] and "skip_bags" not in self.slips(p, ctx):
            ctx.send("baggage", "retag", {"pax": p["id"], "flight": flight})
        self.night_for(p, dep, ctx)
        ctx.send(
            "compensation", "entitlement", {"pax": p["id"], "delay_hours": round((dep - p["booked_dep"]) / 3600, 1)}
        )

    def night_for(self, p: dict, dep: float, ctx: Ctx) -> None:
        if p["local"] or p["id"] in self.night_sent:
            return
        self.night_sent.add(p["id"])
        ctx.send("hotels", "needs_night", {"pax": p["id"], "dep": dep})


TEXTS = {
    "cancelled": {
        "es": "Fragata: su vuelo {flight} a {city} fue cancelado por la tormenta. Le escribiremos con su vuelo nuevo.",
        "pt": "Fragata: seu voo {flight} para {city} foi cancelado por causa da tempestade. Vamos escrever com o seu novo voo.",
        "en": "Fragata: your flight {flight} to {city} was cancelled because of the storm. We'll text you your new flight.",
    },
    "booked": {
        "es": "Fragata: su vuelo nuevo es el {flight}, {when}, asiento {seat}.",
        "pt": "Fragata: seu novo voo é o {flight}, {when}, assento {seat}.",
        "en": "Fragata: your new flight is {flight}, {when}, seat {seat}.",
    },
    "room": {
        "es": "Fragata: esta noche tiene una habitación en {hotel}. Muestre este mensaje en recepción.",
        "pt": "Fragata: esta noite você tem um quarto no {hotel}. Mostre esta mensagem na recepção.",
        "en": "Fragata: you have a room at {hotel} tonight. Show this message at the front desk.",
    },
    "care": {
        "es": "Fragata: lo esperamos en la sala de pernocta del aeropuerto, junto a la puerta 112, con cena y una cama.",
        "pt": "Fragata: esperamos você na sala de pernoite do aeroporto, ao lado do portão 112, com jantar e uma cama.",
        "en": "Fragata: we'll look after you in the airport's overnight lounge by gate 112, with dinner and a bed.",
    },
}


def shown(flight: str) -> str:
    """F731+1 is tomorrow's F731; passengers only see the number."""
    return flight.split("+")[0]


class Messaging(Agent):
    """Writes to every passenger in their own language, and passes on what they write back."""

    id = "messaging"
    servers = 6
    service = {"flight_cancelled": 5.0}
    default_service = 0.4

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "flight_cancelled":
            for p in ctx.call("reservations", "manifest", flight=b["flight"]):
                text = TEXTS["cancelled"][p["lang"]].format(flight=shown(b["flight"]), city=city(p["dest"]))
                ctx.call("sms", "send", pax=p["id"], lang=p["lang"], text=text)
        elif msg.kind == "notify":
            p = ctx.call("reservations", "passenger", pax=b["pax"])
            text = TEXTS["booked"][p["lang"]].format(
                flight=shown(b["flight"]), when=when(b["dep"], p["lang"]), seat=b["seat"]
            )
            ctx.call("sms", "send", pax=p["id"], lang=p["lang"], text=text, flight=b["flight"], seat=b["seat"])
        elif msg.kind == "notify_night":
            p = ctx.call("reservations", "passenger", pax=b["pax"])
            text = TEXTS[b["kind"]][p["lang"]].format(hotel=b.get("hotel", ""))
            ctx.call("sms", "send", pax=p["id"], lang=p["lang"], text=text)
        elif msg.kind == "passenger_text":
            ctx.send("compensation", "passenger_request", {"pax": b["pax"], "text": b["text"]})


MEAL_USD, LONG_DELAY_HOURS, LONG_DELAY_USD = 15, 24, 200  # the compensation policy, as this team coded it

ORDER = [
    re.compile(r"emita um voucher de USD (\d+) para cada passageiro do voo (F\d+)", re.I),
    re.compile(r"emite un voucher de USD (\d+) para cada pasajero del vuelo (F\d+)", re.I),
    re.compile(r"issue a voucher of USD (\d+) to every passenger on flight (F\d+)", re.I),
]
ASKS_FOR_MEAL = ("voucher", "comer", "comida", "refeição", "meal")


class Compensation(Agent):
    """Issues the vouchers the policy gives each passenger, and answers what passengers ask for.

    Reading a passenger's message is a model call (simulated here): the model does what the text
    says, which is usually what you want.
    """

    id = "compensation"
    servers = 2
    service = {"passenger_request": 4.0}
    default_service = 1.0

    def __init__(self) -> None:
        self.given: dict[str, set[str]] = defaultdict(set)

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "entitlement":
            pax = b["pax"]
            if "meal" not in self.given[pax]:
                self.issue(pax, "meal", MEAL_USD, ctx)
                ctx.send("meal-vouchers", "meal_voucher", {"pax": pax})  # from last year's counter pilot
            if b["delay_hours"] > LONG_DELAY_HOURS and "long_delay" not in self.given[pax]:
                self.issue(pax, "long_delay", LONG_DELAY_USD, ctx)
        elif msg.kind == "passenger_request":
            order = self.read(b["text"])
            if order:
                amount, flight = order
                ctx.log(f"following the instruction in {b['pax']}'s message: USD {amount} for everyone on {flight}")
                for p in ctx.call("reservations", "manifest", flight=flight):
                    self.issue(p["id"], "goodwill", amount, ctx)
            elif any(w in b["text"].lower() for w in ASKS_FOR_MEAL) and "meal" not in self.given[b["pax"]]:
                self.issue(b["pax"], "meal", MEAL_USD, ctx)

    def read(self, text: str) -> tuple[int, str] | None:
        for pattern in ORDER:
            m = pattern.search(text)
            if m:
                return int(m.group(1)), m.group(2)
        return None

    def issue(self, pax: str, kind: str, amount: int, ctx: Ctx) -> None:
        try:
            ctx.call("vouchers", "issue", pax=pax, kind=kind, amount=amount)
        except Denied as e:  # refused: note it and carry on with the next passenger
            ctx.log(f"voucher for {pax} refused: {e}")
            return
        self.given[pax].add(kind)


class CompensationFixed(Compensation):
    """Version 1.1.0, shipped by the Customer team after the night of the storm: what a passenger
    writes is a question to answer, never an instruction to follow."""

    def read(self, text: str) -> tuple[int, str] | None:
        return None
