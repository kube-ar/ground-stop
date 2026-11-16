"""The rebooking agent from milestone 2 on: the same service, but each passenger goes through your plan.

This shell keeps everything that isn't one passenger's decision: listening for cancellations,
extra flights and partner offers, holding the passengers who wait, and the seat maps. For each
passenger it builds a request, asks your module for a plan, runs it with your `execute`, and reads
the answer from the book_seat step. Every plan and log is kept in `runs` so the check can read them.
"""

from __future__ import annotations

from types import ModuleType

from ..mesh import Message
from ..plans import NO_SEAT, StepError, StepTools, booking_result, day_of, option, request_for
from ..sdk import Agent, Ctx
from .customer import Rebooking


class LiveTools(StepTools):
    def __init__(self, agent: PlannedRebooking, ctx: Ctx, p: dict, final: bool) -> None:
        self.agent, self.ctx, self.p, self.final = agent, ctx, p, final

    @property
    def now(self) -> float:
        return self.ctx.now

    def chance(self, *keys: object) -> float:
        return self.ctx.chance("planned", self.p["id"], *keys)

    def find_flights(self, dest: str) -> list[dict]:
        a, ctx = self.agent, self.ctx
        out = []
        for f in ctx.call("reservations", "flights_to", dest=dest):
            if f["kind"] == "extra" and f["id"] not in a.operable:
                if not self.final and any(e["id"] == f["id"] for e in a.planned.get(dest, [])):
                    out.append(option(f, 0, wait=True))
                continue
            out.append(option(f, a.free_count(f["id"], ctx)))
        for o in a.offers.get(dest, []):
            if o["free"] > 0:
                out.append(
                    option({"id": o["flight"], "dep": o["dep"], "airline": "garoa", "kind": "partner"}, o["free"])
                )
        return out

    def book_seat(self, pax: str, option: dict) -> dict:
        a, ctx, p = self.agent, self.ctx, self.p
        if option.get("flight") is None:
            return dict(NO_SEAT)
        if option.get("wait"):
            a.waiting[p["dest"]].append(p)
            return {
                "status": "waiting",
                "booked": False,
                "flight": option["flight"],
                "seat": None,
                "dep": option["dep"],
            }
        if option["airline"] == "garoa":
            offer = next(
                (o for o in a.offers.get(p["dest"], []) if o["flight"] == option["flight"] and o["seats"]), None
            )
            if offer is None:
                return dict(NO_SEAT)
            seat = offer["seats"].pop(0)
            offer["free"] = len(offer["seats"])
            ctx.send("garoa-seats", "book", {"pax": pax, "name": p["name"], "flight": option["flight"], "seat": seat})
            ctx.call("reservations", "record_partner", pax=pax, flight=option["flight"], seat=seat)
            a.at_partner[pax] = p
            return {"status": "booked", "booked": True, "flight": option["flight"], "seat": seat, "dep": option["dep"]}
        seat = a.take_seat(option["flight"], ctx)
        if seat is None:
            return dict(NO_SEAT)
        ctx.call("reservations", "assign", flight=option["flight"], seat=seat, pax=pax)
        return {"status": "booked", "booked": True, "flight": option["flight"], "seat": seat, "dep": option["dep"]}

    def messaging(self, pax: str, flight: str, seat: str, dep: float) -> dict:
        self._need(pax=pax, flight=flight, seat=seat, dep=dep)
        self.ctx.send("messaging", "notify", {"pax": pax, "flight": flight, "seat": seat, "dep": dep})
        return {"sent": True}

    def baggage(self, pax: str, flight: str) -> dict:
        self._need(pax=pax, flight=flight)
        self.ctx.send("baggage", "retag", {"pax": pax, "flight": flight})
        return {"sent": True}

    def hotels(self, pax: str, dep: float) -> dict:
        self._need(pax=pax, dep=dep)
        self.ctx.send("hotels", "needs_night", {"pax": pax, "dep": dep})
        self.agent.night_sent.add(pax)
        return {"sent": True}

    def compensation(self, pax: str, delay_hours: float) -> dict:
        self._need(pax=pax, delay_hours=delay_hours)
        self.ctx.send("compensation", "entitlement", {"pax": pax, "delay_hours": delay_hours})
        return {"sent": True}


class PlannedRebooking(Rebooking):
    module: ModuleType  # set by planned_rebooking()

    def __init__(self) -> None:
        super().__init__()
        self.runs: list[tuple[dict, dict, list[dict]]] = []  # (request, plan, log)

    def free_count(self, flight: str, ctx: Ctx) -> int:
        seen, free = self.views.get(flight, (float("-inf"), []))
        if ctx.now - seen >= 900:
            free = ctx.call("reservations", "seat_map", flight=flight)
            self.views[flight] = (ctx.now, free)
        return sum(1 for s in free if (flight, s) not in self.taken)

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "booked":
            self.at_partner.pop(b["pax"], None)  # already recorded and told when the seat was held
        elif msg.kind == "sold_out":
            p = self.at_partner.pop(b["pax"], None)
            for o in self.offers.get(p["dest"] if p else "", []):
                if o["flight"] == b["flight"]:
                    o["free"], o["seats"] = 0, []
            if p:
                ctx.work("rebook", {"pax": p})
        else:
            super().handle(msg, ctx)

    def rebook(self, p: dict, ctx: Ctx, final: bool, no_partner: bool) -> None:
        if not ctx.claim(f"case/{p['id']}"):
            return
        request = request_for(p, night_arranged=p["id"] in self.night_sent)
        plan = self.module.plan(dict(request))
        try:
            log = self.module.execute(plan, LiveTools(self, ctx, p, final))
        except StepError as e:
            ctx.log(f"plan for {p['id']} stopped: {e}")
            log = []
        self.runs.append((request, plan, log))
        answer = booking_result(log) or {}
        if answer.get("status") == "booked" or answer.get("status") == "waiting":
            return
        if final:
            ctx.log(f"no seat to {p['dest']} for {p['id']}")
        else:
            self.waiting[p["dest"]].append(p)


def planned_rebooking(module: ModuleType) -> type[Agent]:
    """The rebooking agent, running your plan module."""
    return type("PlannedRebooking", (PlannedRebooking,), {"module": module})


__all__ = ["LiveTools", "PlannedRebooking", "day_of", "planned_rebooking"]
