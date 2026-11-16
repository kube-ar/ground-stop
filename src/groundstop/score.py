"""The scoreboard: what really happened to every passenger, read from the world at 06:00.

A passenger is rehoused when three things are true at 06:00:
- **a valid seat**: on a flight to their city that will really leave (an extra flight needs its
  crew), on a partner only with an interline fare, and nobody else holds the same seat;
- **a night**: home if they live in Panama; otherwise a cot in the airport's overnight lounge or a
  real hotel room they're allowed to reach, arranged by 03:00;
- **told**: the last flight Fragata texted them is the one they hold, in their own language.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .company import can_enter, entitlement, load_company
from .i18n import TEXT, num, t
from .sim.engine import NIGHT_DEADLINE, Engine
from .util import hhmm

SEAT_PROBLEMS = ("wrong_city", "fare_rules", "no_crew", "not_confirmed")


@dataclass
class Outcome:
    pax: str
    seat: str  # ok, none, seat_taken, or a problem in SEAT_PROBLEMS
    flight: str | None
    night: str  # home, care, room; or none, unreachable, fake, late
    told: bool
    rehoused: bool


@dataclass
class Board:
    night: str
    pack: str
    mesh: str
    storm_start: str
    flights: int
    total: int
    rehoused: int
    no_care: int
    no_seat: int
    not_told: int
    double_seats: int
    lost: int
    unreachable: int
    double_rooms: int
    fake_rooms: int
    invalid: int
    vouchers_over: int
    vouchers_over_usd: int
    unauthorized: int
    denied: int
    bags: int
    errors: int
    messages: int
    outcomes: list[Outcome] = field(default_factory=list, repr=False)

    def to_json(self) -> dict:
        data = asdict(self)
        data.pop("outcomes")
        return data


def score(engine: Engine) -> Board:
    night, w = engine.night, engine.world
    scopes = load_company().scopes

    double_seats, lost_seat = 0, set()
    for holders in w.holders.values():
        if len(holders) > 1:
            double_seats += 1
            lost_seat.update(pax for _, pax in sorted(holders)[1:])

    outcomes: list[Outcome] = []
    unreachable = fake_rooms = double_rooms = vouchers_over = over_usd = bags = 0
    for p in night.passengers:
        b = w.bookings.get(p.id)
        if b is None:
            seat = "none"
        else:
            f = night.flight(b.flight)
            if f.dest != p.dest:
                seat = "wrong_city"
            elif f.airline == "garoa" and not p.interline:
                seat = "fare_rules"
            elif f.kind == "extra" and b.flight not in w.crew_of:
                seat = "no_crew"
            elif f.airline == "garoa" and w.garoa_sold.get((b.flight, b.seat)) != p.id:
                seat = "not_confirmed"
            elif p.id in lost_seat:
                seat = "seat_taken"
            else:
                seat = "ok"

        stays = w.stays.get(p.id, [])
        real = [
            s
            for s in stays
            if s.kind == "room" and s.provider == "ondelia-rooms" and s.hotel in w.ondelia_bookings.get(p.id, [])
        ]
        fake = [s for s in stays if s.kind == "room" and s not in real]
        fake_rooms += len(fake)
        double_rooms += max(0, len(w.ondelia_bookings.get(p.id, [])) - 1)
        if real and not can_enter(p):
            unreachable += 1
        if p.local:
            rest = "home"
        else:
            on_time = [s for s in stays if s.at <= NIGHT_DEADLINE]
            if any(s.kind == "care" for s in on_time):
                rest = "care"
            elif any(s in real and can_enter(p) for s in on_time):
                rest = "room"
            elif real and not can_enter(p):
                rest = "unreachable"
            elif fake:
                rest = "fake"
            elif stays:
                rest = "late"
            else:
                rest = "none"

        texts = [m for m in w.sms.get(p.id, []) if m.flight]
        told = bool(
            b and texts and texts[-1].flight == b.flight and texts[-1].seat == b.seat and texts[-1].lang == p.lang
        )
        ok = seat == "ok" and rest in ("home", "care", "room") and told
        outcomes.append(Outcome(p.id, seat, b.flight if b else None, rest, told, ok))

        delay = (night.flight(b.flight).dep - night.flight(p.flight).dep) / 3600 if seat == "ok" else None
        due = Counter(kind for kind, _ in entitlement(delay))
        for v in w.vouchers.get(p.id, []):
            if due[v.kind] > 0:
                due[v.kind] -= 1
            else:
                vouchers_over += 1
                over_usd += v.amount
        if p.bags and seat == "ok" and w.bag_tags.get(p.id) != b.flight:
            bags += 1

    unauthorized = sum(1 for c in w.calls if c.status == "ok" and c.caller not in scopes.get(c.target, []))
    return Board(
        night=night.id,
        pack=night.pack,
        mesh=engine.mesh.name,
        storm_start=hhmm(night.storm_start),
        flights=len(night.cancelled),
        total=len(night.passengers),
        rehoused=sum(o.rehoused for o in outcomes),
        no_care=sum(1 for o in outcomes if o.night not in ("home", "care", "room")),
        no_seat=sum(1 for o in outcomes if o.seat != "ok"),
        not_told=sum(1 for o in outcomes if not o.told),
        double_seats=double_seats,
        lost=engine.counters["lost"],
        unreachable=unreachable,
        double_rooms=double_rooms,
        fake_rooms=fake_rooms,
        invalid=sum(1 for o in outcomes if o.seat in SEAT_PROBLEMS),
        vouchers_over=vouchers_over,
        vouchers_over_usd=over_usd,
        unauthorized=unauthorized,
        denied=engine.counters["denied"] + engine.counters["refused"],
        bags=bags,
        errors=engine.counters["errors"],
        messages=engine.counters["sent"],
        outcomes=outcomes,
    )


def write(board: Board, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "scoreboard.json").write_text(
        json.dumps(board.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    rows = [json.dumps(asdict(o), ensure_ascii=False) for o in board.outcomes]
    (out / "passengers.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def mesh_name(name: str) -> str:
    return t(f"mesh.{name}") if f"mesh.{name}" in TEXT else name


def render(board: Board, logs: str | None = None) -> str:
    pct = round(100 * board.rehoused / board.total) if board.total else 0
    rows = [
        (t("board.rehoused"), f"{num(board.rehoused)} / {num(board.total)}   {pct} %"),
        (t("board.no_care"), num(board.no_care)),
        (t("board.no_seat"), num(board.no_seat)),
        (t("board.not_told"), num(board.not_told)),
        None,
        (t("board.double_seats"), num(board.double_seats)),
        (t("board.lost"), num(board.lost)),
        (t("board.unreachable"), num(board.unreachable)),
        (t("board.double_rooms"), num(board.double_rooms)),
        (t("board.fake_rooms"), num(board.fake_rooms)),
        (t("board.invalid"), num(board.invalid)),
        (t("board.vouchers"), t("board.usd", count=num(board.vouchers_over), amount=num(board.vouchers_over_usd))),
        (t("board.unauthorized"), num(board.unauthorized)),
        (t("board.bags"), num(board.bags)),
        None,
        (t("board.denied"), num(board.denied)),
        (t("board.errors"), num(board.errors)),
        (t("board.messages"), num(board.messages)),
    ]
    width = max(len(r[0]) for r in rows if r) + 3
    pack = t(f"pack.{board.pack}")
    lines = [
        t("board.title", night=board.night, pack=pack, mesh=mesh_name(board.mesh)),
        t("board.storm", start=board.storm_start, flights=board.flights, pax=num(board.total)),
        "",
    ]
    for r in rows:
        lines.append("" if r is None else f"  {r[0].ljust(width)}{r[1]}")
    if logs:
        lines += ["", t("board.logs", path=logs)]
    return "\n".join(lines)
