"""Operations team: the control center."""

from __future__ import annotations

from ..mesh import Message
from ..sdk import Agent, Ctx


class Disruption(Agent):
    """Cancels what can't fly when the weather closes the airport, and plans extra flights for tomorrow.

    It cancels in waves: what leaves soon goes at once, later departures as the forecast firms up.
    Extra flights need crews, and reserve crews report in over the night, so it asks the crew agent
    for each extra flight at the time the plan says.
    """

    id = "disruption"
    service = {"ground_stop": 20.0}
    default_service = 0.5

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "ground_stop":
            flights = ctx.call("reservations", "departures", start=b["from"], end=b["until"])
            for f in flights:
                ctx.later(f["cancel_at"] - ctx.now, "cancel", {"flight": f["id"], "dest": f["dest"]})
            extras = ctx.call("reservations", "extras")
            plan = [{"id": e["id"], "dest": e["dest"], "dep": e["dep"]} for e in extras]
            ctx.send("rebooking", "extras_planned", {"flights": plan})
            for e in extras:
                ctx.later(e["staff_at"] - ctx.now, "call_crew", {"flight": e["id"]})
            ctx.log(f"ground stop: {len(flights)} departures to cancel tonight, {len(extras)} extra flights planned")
        elif msg.kind == "cancel":
            ctx.call("reservations", "cancel", flight=b["flight"])
            ctx.publish("flight-events", "flight_cancelled", {"flight": b["flight"], "dest": b["dest"]})
        elif msg.kind == "call_crew":
            ctx.send("crew", "staff_flight", {"flight": b["flight"]})
        elif msg.kind in ("flight_operable", "flight_not_operable"):
            ctx.log(f"{b['flight']}: {msg.kind}")


class Crew(Agent):
    """Finds a legal reserve crew for an extra flight. Each assignment takes a few minutes of checks."""

    id = "crew"
    service = {"staff_flight": 180.0}

    def handle(self, msg: Message, ctx: Ctx) -> None:
        if msg.kind != "staff_flight":
            return
        flight = msg.body["flight"]
        crew = ctx.call("crews", "assign", flight=flight)
        if crew:
            ctx.publish("crew-events", "flight_operable", {"flight": flight, "crew": crew})
        else:
            ctx.publish("crew-events", "flight_not_operable", {"flight": flight})
