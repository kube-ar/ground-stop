"""Milestone 0, reference answers for night p1.

How to find them:
- rehoused: the first line of the scoreboard.
- seat_sold_twice: `grep reservations.assign runs/p1/systems.log`, then look for a flight and seat
  that appear twice with different passengers. `sort | uniq -d` on the flight and seat finds them.
- never_reached_crew: `grep LOST runs/p1/traffic.log | grep crew`: the staffing request for one
  extra flight arrived while the crew agent was down.
"""


def answers() -> dict:
    return {
        "rehoused": 491,
        "seat_sold_twice": {"flight": "F419+1", "seat": "1E", "passengers": ["PX-48055", "PX-48058"]},
        "never_reached_crew": "F976+1",
    }
