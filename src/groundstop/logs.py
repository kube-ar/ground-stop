"""Read the logs a replay leaves in runs/<night>/.

traffic.log has one line per message: when, what happened to it, who sent it to whom, its kind,
its body, and why it was lost or denied:

    02:30:00  LOST     disruption -> crew  staff_flight  flight=F976+1  (connection refused: crew is down)

systems.log has one line per call to Fragata's systems:

    18:24:11  rebooking  reservations.assign  flight=F123+1 seat=10E pax=PX-48201  ok
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TRAFFIC = re.compile(r"^(\d\d:\d\d:\d\d)  (\S+)\s+(\S+) -> (\S+)  (\S+)(?:  (.*?))?(?:  \((.*)\))?$")
_SYSTEM = re.compile(r"^(\d\d:\d\d:\d\d)  (\S+)  (\S+)  (.*?)  ?(ok|DENIED \(.*\)|ERROR \(.*\))$")


@dataclass(frozen=True)
class TrafficLine:
    at: str
    status: str  # sent, LOST, REFUSED or DENIED
    sender: str
    to: str  # an agent's name, or an address (http…)
    kind: str
    body: str
    reason: str


@dataclass(frozen=True)
class SystemLine:
    at: str
    caller: str
    target: str  # system.operation, like vouchers.issue
    args: str
    status: str  # ok, DENIED (…) or ERROR (…)


def traffic(path: Path | str) -> list[TrafficLine]:
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = _TRAFFIC.match(raw)
        if m:
            at, status, sender, to, kind, body, reason = m.groups()
            lines.append(TrafficLine(at, status, sender, to, kind, body or "", reason or ""))
    return lines


def system_calls(path: Path | str) -> list[SystemLine]:
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = _SYSTEM.match(raw)
        if m:
            lines.append(SystemLine(*m.groups()))
    return lines


def is_address(name: str) -> bool:
    return name.startswith(("http://", "https://"))
