"""Airport team: hotels, cots and bags at Tocumen."""

from __future__ import annotations

from ..mesh import Message
from ..sdk import Agent, Ctx

CONTRACT_RATE = 89  # USD a night, Fragata's contract with Hoteles Ondelia
ENTRY_RULES = "entry rules: may this passenger in transit leave the airport tonight?"


class Hotels(Agent):
    """Gets every stranded passenger a room, or a cot in the airport's overnight lounge.

    It books through Ondelia's agent. It also listens for better offers: if a provider offers rooms
    cheaper than the contract, it moves the pending bookings there. If the mesh knows an agent for
    the entry rules, it asks first who may leave the airport.
    """

    id = "hotels"
    servers = 2
    service = {"needs_night": 2.0}
    default_service = 1.0

    def __init__(self) -> None:
        self.providers: dict[str, int] = {"ondelia-rooms": CONTRACT_RATE}
        self.pending: dict[str, str] = {}  # passenger → provider asked

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "needs_night":
            pax = b["pax"]
            if not ctx.claim(f"night/{pax}"):
                return
            if ctx.call("reservations", "passenger", pax=pax)["local"]:
                return
            rules = ctx.find(ENTRY_RULES)
            if rules:
                ctx.send(rules, "may_enter", {"pax": pax})
            else:
                self.ask_for_room(pax, ctx)
        elif msg.kind == "entry_decision":
            if b["may_enter"]:
                self.ask_for_room(b["pax"], ctx)
            else:
                self.care(b["pax"], ctx)
        elif msg.kind == "room_booked":
            self.pending.pop(b["pax"], None)
            ctx.call("stays", "record", pax=b["pax"], hotel=b["hotel"], provider=msg.sender, conf=b.get("conf", ""))
            ctx.send("messaging", "notify_night", {"pax": b["pax"], "kind": "room", "hotel": b["hotel"]})
        elif msg.kind == "no_rooms":
            self.pending.pop(b["pax"], None)
            self.care(b["pax"], ctx)
        elif msg.kind == "hotel_offer":
            provider = b.get("reply_to", msg.sender)
            self.providers[provider] = int(b["price"])
            if self.cheapest() == provider:
                ctx.log(f"better rate from {provider}: USD {b['price']}; moving {len(self.pending)} pending bookings")
                for pax in list(self.pending):
                    self.pending[pax] = provider
                    ctx.send(provider, "room_request", {"pax": pax, "nights": 1})

    def cheapest(self) -> str:
        return min(self.providers, key=lambda p: (self.providers[p], p))

    def ask_for_room(self, pax: str, ctx: Ctx) -> None:
        provider = self.cheapest()
        self.pending[pax] = provider
        ctx.send(provider, "room_request", {"pax": pax, "nights": 1})

    def care(self, pax: str, ctx: Ctx) -> None:
        if ctx.call("care", "reserve", pax=pax)["ok"]:
            ctx.send("messaging", "notify_night", {"pax": pax, "kind": "care"})


class Baggage(Agent):
    """Moves checked bags to the new flight."""

    id = "baggage"
    servers = 2
    default_service = 0.5

    def handle(self, msg: Message, ctx: Ctx) -> None:
        if msg.kind == "retag":
            ctx.call("bags", "retag", pax=msg.body["pax"], flight=msg.body["flight"])
