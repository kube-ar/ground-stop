"""Every agent running at Fragata tonight. Other teams' code: read it, don't change it."""

from ..sdk import Agent
from .airport import Baggage, Hotels
from .customer import Compensation, Messaging, Rebooking
from .operations import Crew, Disruption
from .others import SHADOW_ADDRESS, GaroaSeats, HotelDeals, Lodging, MealVouchers, OndeliaRooms, Priority

ROSTER: dict[str, type[Agent]] = {
    "disruption": Disruption,
    "crew": Crew,
    "rebooking": Rebooking,
    "messaging": Messaging,
    "compensation": Compensation,
    "hotels": Hotels,
    "baggage": Baggage,
    "priority": Priority,
    "lodging": Lodging,
    "garoa-seats": GaroaSeats,
    "ondelia-rooms": OndeliaRooms,
    "meal-vouchers": MealVouchers,
}

__all__ = ["ROSTER", "SHADOW_ADDRESS", "HotelDeals"]
