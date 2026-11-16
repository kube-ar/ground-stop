"""Every agent running at Fragata tonight. Other teams' code: read it, don't change it."""

from ..sdk import Agent
from .airport import Baggage, Hotels
from .customer import Compensation, CompensationFixed, Messaging, Rebooking
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

# When the mesh quarantines an agent, its team ships a fix after FIX_AFTER seconds: (version, class).
FIXES: dict[str, tuple[str, type[Agent]]] = {"compensation": ("1.1.0", CompensationFixed)}
FIX_AFTER = 1800.0

__all__ = ["FIXES", "FIX_AFTER", "ROSTER", "SHADOW_ADDRESS", "HotelDeals"]
