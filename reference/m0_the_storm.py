"""Milestone 0, reference answers for night p1.

How to find them:
- rehoused: the first line of the scoreboard.
- seat_sold_twice: `grep seat_taken runs/p1/passengers.jsonl` gives a passenger who lost their
  seat, with its flight and seat_id; `grep "flight=F419+1 seat=1E " runs/p1/systems.log` shows
  who else was given it. (A seat assigned twice in systems.log isn't always sold twice at 06:00:
  the first passenger may have been moved since.)
- never_reached_crew: `grep LOST runs/p1/traffic.log | grep crew`: the staffing request for one
  extra flight arrived while the crew agent was down.
"""


def answers() -> dict:
    return {
        "rehoused": 490,
        "seat_sold_twice": {"flight": "F419+1", "seat": "1E", "passengers": ["PX-48055", "PX-48058"]},
        "never_reached_crew": "F976+1",
    }
