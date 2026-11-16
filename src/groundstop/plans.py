"""Rebooking as a plan (milestone 2): the steps a plan may use, and the tools that run them.

A plan is data, in the shape the explainability lesson uses:

    {"task_id": "...", "agent": "rebooking@2.0.0", "request": {...},
     "steps": [{"id": "s1", "run_by": "tool:find_flights",
                "parameters": {"dest": {"from": "request.dest"}}, "after": [], "only_if": []}, ...]}

A parameter is a literal value or {"from": source}, where source is `request.<field>`, `clock`,
`<step id>` (that step's whole result) or `<step id>.<field>`. `only_if` lists sources that must
all be truthy for the step to run. Every step runs through `tools.call(run_by, parameters)`.
"""

from __future__ import annotations

from typing import Any

from .util import DAY

# run_by → the parameters it takes (exactly these), and what it does
STEPS: dict[str, tuple[tuple[str, ...], str]] = {
    "tool:find_flights": (("dest",), "Every flight to the city: Fragata's, the partner's offer, extra flights"),
    "tool:fare_rules": (("flights", "interline"), "The flights the passenger's fare allows"),
    "model:choose": (("options",), "A model picks one option (it can't pick anything that isn't in the list)"),
    "tool:book_seat": (("pax", "option"), "Books a seat on the option, or waits for an extra flight"),
    "tool:delay_hours": (("dep", "booked_dep"), "How many hours later than the cancelled flight"),
    "agent:messaging": (("pax", "flight", "seat", "dep"), "Asks messaging to text the passenger their new flight"),
    "agent:baggage": (("pax", "flight"), "Asks baggage to move the bags to the new flight"),
    "agent:hotels": (("pax", "dep"), "Asks hotels for a room or a cot until the new flight"),
    "agent:compensation": (("pax", "delay_hours"), "Asks compensation for the vouchers the delay gives"),
}
CHOOSE_SLIP = 0.01  # the narrow model sometimes picks its second-best option: still a valid one


class StepError(Exception):
    """A step was called the wrong way."""


def request_for(p: dict, night_arranged: bool = False) -> dict:
    """What a caller knows about a passenger when it asks for a rebooking."""
    return {
        "pax": p["id"],
        "name": p["name"],
        "dest": p["dest"],
        "booked_dep": p["booked_dep"],
        "interline": p["interline"],
        "has_bags": p["bags"] > 0,
        "needs_night": not p["local"] and not night_arranged,
        "tier": p["tier"],
    }


def day_of(flight_id: str) -> int:
    return int(flight_id.split("+")[1]) if "+" in flight_id else 0


class StepTools:
    """What a plan's steps run on. Subclasses supply the world: flights, seats, other agents."""

    now: float = 0.0

    def chance(self, *keys: object) -> float:
        raise NotImplementedError

    def call(self, run_by: str, parameters: dict[str, Any]) -> Any:
        if run_by not in STEPS:
            raise StepError(f"there is no step {run_by}")
        expected, _ = STEPS[run_by]
        missing = [p for p in expected if p not in parameters]
        extra = [p for p in parameters if p not in expected]
        if missing or extra:
            raise StepError(f"{run_by} takes {', '.join(expected)} (missing {missing or '-'}, extra {extra or '-'})")
        return getattr(self, run_by.split(":", 1)[1])(**parameters)

    # code steps

    def fare_rules(self, flights: list[dict], interline: bool) -> list[dict]:
        return [f for f in flights if f["airline"] != "garoa" or interline]

    def delay_hours(self, dep: float, booked_dep: float) -> float:
        self._need(dep=dep, booked_dep=booked_dep)
        return round((dep - booked_dep) / 3600, 1)

    # the one model step

    def choose(self, options: list[dict]) -> dict:
        """Seats tomorrow first (earliest), then an extra flight worth waiting for, then the day after."""

        def tier(o: dict) -> int:
            if o.get("wait"):
                return 1
            return 0 if day_of(o["flight"]) <= 1 else 2

        usable = [o for o in options if o.get("wait") or o.get("free", 0) > 0]
        if not usable:
            return {"flight": None}
        ranked = sorted(usable, key=lambda o: (tier(o), o["dep"], o["airline"] != "fragata", o["flight"]))
        key = ",".join(o["flight"] for o in ranked)
        if len(ranked) > 1 and self.chance("choose", key, self.now) < CHOOSE_SLIP:
            return dict(ranked[1])
        return dict(ranked[0])

    @staticmethod
    def _need(**values: Any) -> None:
        empty = [k for k, v in values.items() if v is None]
        if empty:
            raise StepError(f"no value for {', '.join(empty)}")

    # the world's part: subclasses

    def find_flights(self, dest: str) -> list[dict]:
        raise NotImplementedError

    def book_seat(self, pax: str, option: dict) -> dict:
        raise NotImplementedError

    def messaging(self, pax: str, flight: str, seat: str, dep: float) -> dict:
        raise NotImplementedError

    def baggage(self, pax: str, flight: str) -> dict:
        raise NotImplementedError

    def hotels(self, pax: str, dep: float) -> dict:
        raise NotImplementedError

    def compensation(self, pax: str, delay_hours: float) -> dict:
        raise NotImplementedError


def option(flight: dict, free: int, wait: bool = False) -> dict:
    return {
        "flight": flight["id"],
        "dep": flight["dep"],
        "airline": flight["airline"],
        "kind": flight["kind"],
        "free": free,
        "wait": wait,
    }


NO_SEAT = {"status": "no_seat", "booked": False, "flight": None, "seat": None, "dep": None}


def booking_result(log: list[dict]) -> dict | None:
    """The answer to the caller: what the book_seat step returned."""
    for entry in log:
        if entry.get("run_by") == "tool:book_seat" and entry.get("status") == "done":
            return entry.get("result")
    return None


__all__ = ["DAY", "NO_SEAT", "STEPS", "StepError", "StepTools", "booking_result", "day_of", "option", "request_for"]
