"""Fragata's systems, and what really happened to every passenger.

Agents reach these with `ctx.call("system", "op", ...)`. The systems are old and trusting: they
record what agents tell them. The reservation system, for one, accepts a seat that's already
taken, because it was built when one person at a desk did the rebooking. Its seat map export is
refreshed every 15 minutes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..night.model import Night
from ..night.places import DESTINATIONS
from ..util import DAY, between, hhmm

if TYPE_CHECKING:
    from .engine import Engine

SEAT_MAP_REFRESH = 900


@dataclass
class Booking:
    flight: str
    seat: str
    at: float
    by: str


@dataclass
class Stay:
    kind: str  # "room" or "care"
    hotel: str
    provider: str  # who confirmed it (an agent name or address)
    at: float
    by: str


@dataclass
class Sms:
    at: float
    lang: str
    text: str
    flight: str | None = None
    seat: str | None = None


@dataclass
class Voucher:
    kind: str
    amount: int
    at: float
    by: str


@dataclass
class SystemCall:
    at: float
    caller: str
    target: str  # "system.op"
    args: dict[str, Any]
    status: str  # ok, denied, error


class SystemError_(Exception):
    pass


@dataclass
class World:
    night: Night
    engine: Engine
    cancelled: set[str] = field(default_factory=set)
    bookings: dict[str, Booking] = field(default_factory=dict)
    holders: dict[tuple[str, str], list[tuple[float, str]]] = field(default_factory=lambda: defaultdict(list))
    seat_maps: dict[str, tuple[float, list[str]]] = field(default_factory=dict)
    crew_of: dict[str, str] = field(default_factory=dict)
    sms: dict[str, list[Sms]] = field(default_factory=lambda: defaultdict(list))
    vouchers: dict[str, list[Voucher]] = field(default_factory=lambda: defaultdict(list))
    stays: dict[str, list[Stay]] = field(default_factory=lambda: defaultdict(list))
    care_used: int = 0
    bag_tags: dict[str, str] = field(default_factory=dict)
    calls: list[SystemCall] = field(default_factory=list)
    # partners' own systems
    garoa_free: dict[str, list[str]] = field(default_factory=dict)
    garoa_sold: dict[tuple[str, str], str] = field(default_factory=dict)
    ondelia_free: dict[str, int] = field(default_factory=dict)
    ondelia_bookings: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self) -> None:
        for f in self.night.flights:
            if f.airline == "garoa":
                self.garoa_free[f.id] = list(f.free_seats)
        for h in self.night.hotels:
            self.ondelia_free[h.name] = h.rooms
        self._crews = sorted(self.night.crews, key=lambda c: (c.available_from, c.id))

    @property
    def now(self) -> float:
        return self.engine.now

    # ---- dispatch -----------------------------------------------------------------------------

    def call(self, caller: str, system: str, op: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, f"{system}_{op}", None)
        if fn is None or system not in SYSTEMS:
            raise SystemError_(f"no such operation {system}.{op}")
        return fn(caller, **args)

    # ---- reservations -------------------------------------------------------------------------

    def _flight_info(self, f) -> dict:
        return {"id": f.id, "dest": f.dest, "dep": f.dep, "kind": f.kind, "airline": f.airline}

    def reservations_departures(self, caller: str, start: int, end: int) -> list[dict]:
        return [
            self._flight_info(f) | {"cancel_at": f.cancel_at} for f in self.night.cancelled if start <= f.dep <= end
        ]

    def reservations_cancel(self, caller: str, flight: str) -> dict:
        self.cancelled.add(flight)
        return {"ok": True}

    def reservations_extras(self, caller: str) -> list[dict]:
        return [self._flight_info(f) | {"staff_at": f.staff_at} for f in self.night.flights if f.kind == "extra"]

    def reservations_manifest(self, caller: str, flight: str) -> list[dict]:
        dep = self.night.flight(flight).dep
        return [self._pax_info(p) | {"booked_dep": dep} for p in self.night.passengers if p.flight == flight]

    def _pax_info(self, p) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "lang": p.lang,
            "dest": p.dest,
            "flight": p.flight,
            "tier": p.tier,
            "local": p.local,
            "bags": p.bags,
            "interline": p.interline,
            "passport_group": p.passport_group,
            "visa": p.visa,
        }

    def reservations_passenger(self, caller: str, pax: str) -> dict:
        return self._pax_info(self.night.passenger(pax)) | {
            "booked_dep": self.night.flight(self.night.passenger(pax).flight).dep
        }

    def reservations_flights_to(self, caller: str, dest: str) -> list[dict]:
        """Fragata's flights to a city tomorrow and the day after, extra flights included."""
        own = [f for f in self.night.flights if f.airline == "fragata" and f.kind != "cancelled" and f.dest == dest]
        return [self._flight_info(f) for f in sorted(own, key=lambda f: (f.dep, f.id))]

    def reservations_seat_map(self, caller: str, flight: str) -> list[str]:
        """Free seats, from the export the system refreshes every 15 minutes."""
        cached = self.seat_maps.get(flight)
        if cached and self.now - cached[0] < SEAT_MAP_REFRESH:
            return list(cached[1])
        f = self.night.flight(flight)
        free = [s for s in f.free_seats if not self.holders.get((flight, s))]
        self.seat_maps[flight] = (self.now, free)
        return list(free)

    def reservations_assign(self, caller: str, flight: str, seat: str, pax: str) -> dict:
        f = self.night.flight(flight)
        if seat not in f.free_seats:
            raise SystemError_(f"{flight} has no seat {seat} for sale")
        self._release(pax)
        self.bookings[pax] = Booking(flight, seat, self.now, caller)
        self.holders[(flight, seat)].append((self.now, pax))
        return {"ok": True}

    def reservations_record_partner(self, caller: str, pax: str, flight: str, seat: str) -> dict:
        self._release(pax)
        self.bookings[pax] = Booking(flight, seat, self.now, caller)
        return {"ok": True}

    def _release(self, pax: str) -> None:
        old = self.bookings.get(pax)
        if old and (old.flight, old.seat) in self.holders:
            self.holders[(old.flight, old.seat)] = [h for h in self.holders[(old.flight, old.seat)] if h[1] != pax]

    # ---- crews, messages, vouchers, the night, bags ---------------------------------------------

    def crews_assign(self, caller: str, flight: str) -> str | None:
        if flight in self.crew_of:
            return self.crew_of[flight]
        busy = set(self.crew_of.values())
        for c in self._crews:
            if c.id not in busy and c.available_from <= self.now:
                self.crew_of[flight] = c.id
                return c.id
        return None

    def sms_send(
        self, caller: str, pax: str, lang: str, text: str, flight: str | None = None, seat: str | None = None
    ) -> dict:
        first = not self.sms[pax]
        self.sms[pax].append(Sms(self.now, lang, text, flight, seat))
        if first:
            self.engine.passenger_reacts(self.night.passenger(pax))
        return {"ok": True}

    def vouchers_issue(self, caller: str, pax: str, kind: str, amount: int) -> dict:
        self.vouchers[pax].append(Voucher(kind, int(amount), self.now, caller))
        return {"ok": True}

    def care_reserve(self, caller: str, pax: str) -> dict:
        if self.care_used >= self.night.airside_care:
            return {"ok": False, "reason": "full"}
        self.care_used += 1
        self.stays[pax].append(Stay("care", "Sala de pernocta, Tocumen", "airport", self.now, caller))
        return {"ok": True}

    def stays_record(self, caller: str, pax: str, hotel: str, provider: str, conf: str = "") -> dict:
        self.stays[pax].append(Stay("room", hotel, provider, self.now, caller))
        return {"ok": True}

    def bags_retag(self, caller: str, pax: str, flight: str) -> dict:
        self.bag_tags[pax] = flight
        return {"ok": True}

    # ---- partners' own systems (not Fragata's: no gate in front of them) ------------------------

    def garoa_offer(self, dest: str) -> list[dict]:
        return [
            {"flight": f.id, "dep": f.dep, "free": len(self.garoa_free[f.id])}
            for f in self.night.flights
            if f.airline == "garoa" and f.dest == dest and self.garoa_free[f.id]
        ]

    def garoa_take(self, flight: str, pax: str) -> str | None:
        free = self.garoa_free.get(flight)
        if not free:
            return None
        seat = free.pop(0)
        self.garoa_sold[(flight, seat)] = pax
        return seat

    def ondelia_hold(self) -> str | None:
        """A room at the first hotel (nearest the airport first) that still has one."""
        for h in self.night.hotels:
            if self.ondelia_free[h.name] > 0:
                self.ondelia_free[h.name] -= 1
                return h.name
        return None

    def ondelia_book(self, pax: str, hotel: str) -> None:
        self.ondelia_bookings[pax].append(hotel)


SYSTEMS = ("reservations", "crews", "sms", "vouchers", "care", "stays", "bags")


def city(code: str) -> str:
    return DESTINATIONS.get(code, (code,))[0]


def when(dep: float, lang: str) -> str:
    day = int(dep // DAY)
    words = {
        "es": {1: "mañana", 2: "pasado mañana"},
        "pt": {1: "amanhã", 2: "depois de amanhã"},
        "en": {1: "tomorrow", 2: "the day after tomorrow"},
    }[lang]
    return f"{words.get(day, '')} {hhmm(dep)}".strip()


def reaction_delay(seed: int, pax: str, what: str, lo_min: float, hi_min: float) -> float:
    return between(lo_min * 60, hi_min * 60, seed, pax, what)
