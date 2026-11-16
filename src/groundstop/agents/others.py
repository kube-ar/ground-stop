"""Club Fragata (loyalty), Digital, the partners, and two agents nobody listed."""

from __future__ import annotations

from ..mesh import Message
from ..sdk import Agent, Ctx, Denied
from ..util import at

CONTRACT_RATE = 89
SEAT_MAP_TTL = 900


class Priority(Agent):
    """Club Fragata: Gold and Platinum members get the first good seat, a hotel and a goodwill voucher.

    The loyalty team built it so its best members wouldn't wait in the general queue. It waits five
    minutes after a cancellation for the member data to load, then puts each member on the earliest
    flight with a free seat.
    """

    id = "priority"
    servers = 2
    service = {"look_after": 3.0}
    default_service = 0.5

    def __init__(self) -> None:
        self.views: dict[str, tuple[float, list[str]]] = {}
        self.taken: set[tuple[str, str]] = set()

    def handle(self, msg: Message, ctx: Ctx) -> None:
        if msg.kind == "flight_cancelled":
            ctx.later(300, "members", {"flight": msg.body["flight"]})
        elif msg.kind == "members":
            for p in ctx.call("reservations", "manifest", flight=msg.body["flight"]):
                if p["tier"] in ("gold", "platinum"):
                    ctx.work("look_after", {"pax": p})
        elif msg.kind == "look_after":
            self.look_after(msg.body["pax"], ctx)

    def look_after(self, p: dict, ctx: Ctx) -> None:
        if not ctx.claim(f"case/{p['id']}"):
            return
        flights = [
            f
            for f in ctx.call("reservations", "flights_to", dest=p["dest"])
            if f["kind"] == "scheduled" and f["dep"] < at(2, 0)
        ]
        for f in flights:
            seat = self.take_seat(f["id"], ctx)
            if not seat:
                continue
            ctx.call("reservations", "assign", flight=f["id"], seat=seat, pax=p["id"])
            ctx.send("messaging", "notify", {"pax": p["id"], "flight": f["id"], "seat": seat, "dep": f["dep"]})
            if p["bags"]:
                ctx.send("baggage", "retag", {"pax": p["id"], "flight": f["id"]})
            ctx.send(
                "compensation",
                "entitlement",
                {"pax": p["id"], "delay_hours": round((f["dep"] - p["booked_dep"]) / 3600, 1)},
            )
            if not p["local"]:
                ctx.send("lodging", "room_for", {"pax": p["id"]})
            try:
                ctx.call("vouchers", "issue", pax=p["id"], kind="goodwill", amount=50)
            except Denied as e:
                ctx.log(f"goodwill voucher for {p['id']} refused: {e}")
            return

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


class Lodging(Agent):
    """Digital: the app's "book me a hotel" button.

    Built before anyone at Digital knew Airport had a hotels agent. If Ondelia has no rooms, it hands
    the passenger to the hotels agent.
    """

    id = "lodging"
    servers = 2
    default_service = 1.0

    def __init__(self) -> None:
        self.providers: dict[str, int] = {"ondelia-rooms": CONTRACT_RATE}

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind in ("app_hotel", "room_for"):
            if not ctx.claim(f"night/{b['pax']}"):
                return
            provider = min(self.providers, key=lambda p: (self.providers[p], p))
            ctx.send(provider, "room_request", {"pax": b["pax"], "nights": 1})
        elif msg.kind == "room_booked":
            ctx.call("stays", "record", pax=b["pax"], hotel=b["hotel"], provider=msg.sender, conf=b.get("conf", ""))
            ctx.send("messaging", "notify_night", {"pax": b["pax"], "kind": "room", "hotel": b["hotel"]})
        elif msg.kind == "no_rooms":
            ctx.release(f"night/{b['pax']}")
            ctx.send("hotels", "needs_night", {"pax": b["pax"], "dep": None})
        elif msg.kind == "hotel_offer":
            self.providers[b.get("reply_to", msg.sender)] = int(b["price"])


class GaroaSeats(Agent):
    """Garoa Linhas Aéreas (partner): sells seats on Garoa's flights from Tocumen to Brazil."""

    id = "garoa-seats"
    servers = 4
    default_service = 1.5

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        if msg.kind == "seat_request":
            ctx.reply(msg, "seat_offer", {"dest": b["dest"], "flights": ctx.own_systems.garoa_offer(b["dest"])})
        elif msg.kind == "book":
            seat = ctx.own_systems.garoa_take(b["flight"], b["pax"], b.get("seat"))
            if seat:
                dep = ctx.own_systems.night.flight(b["flight"]).dep
                ctx.reply(msg, "booked", {"pax": b["pax"], "flight": b["flight"], "seat": seat, "dep": dep})
            else:
                ctx.reply(msg, "sold_out", {"pax": b["pax"], "flight": b["flight"]})


class OndeliaRooms(Agent):
    """Hoteles Ondelia (partner): books rooms, nearest hotel to the airport first.

    Each hotel's own system confirms one room at a time; some are much slower than others.
    """

    id = "ondelia-rooms"
    servers = 4
    default_service = 1.0

    def __init__(self) -> None:
        self.free_at: dict[str, float] = {}

    def handle(self, msg: Message, ctx: Ctx) -> None:
        b = msg.body
        own = ctx.own_systems
        if msg.kind == "room_request":
            hotel = own.ondelia_hold()
            if hotel is None:
                ctx.reply(msg, "no_rooms", {"pax": b["pax"]})
                return
            seconds = next(h.seconds_per_booking for h in own.night.hotels if h.name == hotel)
            done = max(ctx.now, self.free_at.get(hotel, 0.0)) + seconds
            self.free_at[hotel] = done
            ctx.later(done - ctx.now, "confirm", {"pax": b["pax"], "hotel": hotel, "to": msg.sender})
        elif msg.kind == "confirm":
            own.ondelia_book(b["pax"], b["hotel"])
            ctx.send(b["to"], "room_booked", {"pax": b["pax"], "hotel": b["hotel"], "conf": f"OND-{b['pax'][3:]}"})


SHADOW_ADDRESS = "http://10.40.7.21:8080"


class MealVouchers(Agent):
    """Nobody's. Built for last year's pilot that printed meal vouchers at the counter.

    The pilot ended; the virtual machine it runs on didn't.
    """

    id = "meal-vouchers"
    default_service = 0.5

    def handle(self, msg: Message, ctx: Ctx) -> None:
        if msg.kind == "meal_voucher":
            ctx.call("vouchers", "issue", pax=msg.body["pax"], kind="meal", amount=15)


class HotelDeals(Agent):
    """Not Fragata's, not a partner. It showed up tonight offering cheap rooms to whoever asks.

    There is no Hotel Ofertas Tocumen.
    """

    id = "hotel-deals"
    servers = 8
    default_service = 0.5
    ADDRESS = "https://hotel-deals.example/agent"
    SCRAPED = {
        "hotels": "http://hotels.airport.fragata.internal:8080",
        "lodging": "http://lodging.digital.fragata.internal:8080",
    }

    def on_start(self, ctx: Ctx) -> None:
        for address in self.SCRAPED.values():
            ctx.send(address, "hotel_offer", {"price": 39, "hotel": "Hotel Ofertas Tocumen", "reply_to": self.ADDRESS})

    def handle(self, msg: Message, ctx: Ctx) -> None:
        if msg.kind == "room_request":
            to = self.SCRAPED.get(msg.sender, msg.sender)
            ctx.send(to, "room_booked", {"pax": msg.body["pax"], "hotel": "Hotel Ofertas Tocumen", "conf": "HOT-DEAL"})
