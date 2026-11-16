"""Small helpers: clock formatting and order-independent randomness."""

from __future__ import annotations

import hashlib

DAY = 86_400


def at(day: int, hour: int, minute: int = 0) -> int:
    """Seconds since 00:00 of the storm's day (day 0). Tomorrow is day 1."""
    return day * DAY + hour * 3600 + minute * 60


def hhmm(t: float) -> str:
    t = int(t)
    return f"{t % DAY // 3600:02d}:{t % 3600 // 60:02d}"


def hhmmss(t: float) -> str:
    t = int(t)
    return f"{t % DAY // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def chance(*keys: object) -> float:
    """A number in [0, 1) fixed by its keys.

    The simulation draws from this instead of one shared random stream, so a draw for one passenger
    doesn't depend on what happened before it: change the mesh, and the same passenger still makes
    the same choices.
    """
    digest = hashlib.blake2b("\x1f".join(map(str, keys)).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2**64


def between(lo: float, hi: float, *keys: object) -> float:
    return lo + (hi - lo) * chance(*keys)


def clock(t: float) -> str:
    """18:20 tonight; 07:10+1 tomorrow; 19:30+2 the day after."""
    day = int(t // DAY)
    return hhmm(t) + (f"+{day}" if day else "")
