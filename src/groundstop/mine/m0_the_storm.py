"""Milestone 0, the storm: replay night p1 with today's mesh and read what went wrong.

1. Replay it: `uv run ground-stop replay` (or `docker compose up`).
2. Read the scoreboard, then the logs it left in runs/p1/.
3. Write what you found in `answers()` and run `uv run ground-stop check 0`.

Instructions: https://kube.ar/es/agentic-mesh/project/ground-stop/the-storm
"""


def answers() -> dict:
    # Replace the raise below with your answers, in this shape:
    #
    # return {
    #     "rehoused": 123,                 # the scoreboard's first line: how many were rehoused by 06:00
    #     "seat_sold_twice": {             # one seat two passengers ended up holding (systems.log)
    #         "flight": "F123+1",
    #         "seat": "14C",
    #         "passengers": ["PX-10001", "PX-10002"],
    #     },
    #     "never_reached_crew": "F901+1",  # the extra flight whose crew request was lost (traffic.log)
    # }
    raise NotImplementedError("Replay night p1 and read runs/p1/ first")
