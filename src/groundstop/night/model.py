"""What a night is made of: flights, passengers, hotels, crews and the events the storm brings.

Times are seconds since 00:00 of the storm's day (day 0); tomorrow is day 1. A flight id carries
its day: F731 leaves tonight, F731+1 tomorrow, F731+2 the day after.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

AIRCRAFT = {"E190": 100, "B738": 160, "B39M": 174}


def seat_ids(aircraft: str) -> list[str]:
    """Seat numbers in boarding order: E190 is 2-2, the Boeings 3-3."""
    letters = "ABCD" if aircraft == "E190" else "ABCDEF"
    seats = [f"{row}{letter}" for row in range(1, 40) for letter in letters]
    return seats[: AIRCRAFT[aircraft]]


@dataclass
class Flight:
    id: str
    airline: str  # "fragata" or "garoa"
    kind: str  # "cancelled" (tonight), "scheduled", "extra" (added for the storm) or "partner"
    dest: str
    dep: int
    aircraft: str
    free_seats: list[str] = field(default_factory=list)  # seats still for sale when the storm hits
    staff_at: int | None = None  # extra flights: when the operations team asks for a crew
    cancel_at: int | None = None  # tonight's flights: when operations cancels it (in waves, as the forecast updates)

    @property
    def capacity(self) -> int:
        return AIRCRAFT[self.aircraft]


@dataclass
class Passenger:
    id: str
    name: str
    lang: str  # es, pt or en: the language messages must be written in
    flight: str  # tonight's cancelled flight
    dest: str
    origin: str  # where the trip began; PTY for people who started in Panama
    local: bool  # lives in Panama: goes home for the night
    tier: str  # none, silver, gold or platinum (Club Fragata)
    passport_group: int  # 1, 2 or 3 under the entry rules (company/entry-rules.toml)
    visa: bool
    bags: int
    app: bool  # uses the Fragata app, which can book a hotel on its own
    interline: bool  # the fare allows a seat on a partner airline
    writes: bool  # will text back to ask about a meal voucher


@dataclass
class Hotel:
    id: str
    name: str
    rooms: int
    seconds_per_booking: int  # how long the hotel's own system takes to confirm one room


@dataclass
class Crew:
    id: str
    available_from: int


@dataclass
class Event:
    at: int
    type: str  # ground_stop, partner_moves, crash, intruder, injection
    data: dict = field(default_factory=dict)


@dataclass
class Night:
    id: str
    pack: str
    seed: int
    storm_start: int
    storm_end: int
    flights: list[Flight]
    passengers: list[Passenger]
    hotels: list[Hotel]
    crews: list[Crew]
    airside_care: int  # cots and lounge places inside the airport
    events: list[Event]

    def flight(self, fid: str) -> Flight:
        return self._flights[fid]

    def passenger(self, pid: str) -> Passenger:
        return self._pax[pid]

    def __post_init__(self) -> None:
        self._flights = {f.id: f for f in self.flights}
        self._pax = {p.id: p for p in self.passengers}

    @property
    def cancelled(self) -> list[Flight]:
        return [f for f in self.flights if f.kind == "cancelled"]

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "pack": self.pack,
            "seed": self.seed,
            "storm_start": self.storm_start,
            "storm_end": self.storm_end,
            "airside_care": self.airside_care,
            "flights": [asdict(f) for f in self.flights],
            "hotels": [asdict(h) for h in self.hotels],
            "crews": [asdict(c) for c in self.crews],
            "events": [asdict(e) for e in self.events],
            "passengers": [asdict(p) for p in self.passengers],
        }

    @classmethod
    def from_json(cls, data: dict) -> Night:
        return cls(
            id=data["id"],
            pack=data["pack"],
            seed=data["seed"],
            storm_start=data["storm_start"],
            storm_end=data["storm_end"],
            airside_care=data["airside_care"],
            flights=[Flight(**f) for f in data["flights"]],
            hotels=[Hotel(**h) for h in data["hotels"]],
            crews=[Crew(**c) for c in data["crews"]],
            events=[Event(**e) for e in data["events"]],
            passengers=[Passenger(**p) for p in data["passengers"]],
        )


def save(night: Night, path: Path) -> None:
    """One line per flight and passenger, so a diff or a grep stays readable."""
    data = night.to_json()
    lines = ["{"]
    keys = list(data)
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        value = data[key]
        if isinstance(value, list):
            lines.append(f'  "{key}": [')
            for j, item in enumerate(value):
                lines.append("    " + json.dumps(item, ensure_ascii=False) + ("," if j < len(value) - 1 else ""))
            lines.append(f"  ]{comma}")
        else:
            lines.append(f'  "{key}": {json.dumps(value, ensure_ascii=False)}{comma}')
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load(path: Path) -> Night:
    return Night.from_json(json.loads(path.read_text(encoding="utf-8")))
