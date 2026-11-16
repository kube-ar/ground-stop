"""A small check runner: runs your functions and says what's right, what isn't, and what to read."""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from ..i18n import lang, t
from ..milestones import Lesson, Milestone

MAX_DETAILS = 4


class NotStarted(Exception):
    """Your function still raises NotImplementedError."""


@dataclass
class Result:
    name: dict[str, str]  # per language
    lesson: Lesson | None
    passed: bool = True
    started: bool = True
    score: str = ""
    details: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, line: str) -> None:
        self.passed = False
        self.details.append(line)


def attempt(result: Result, fn: Callable, *args, none_ok: bool = False, **kwargs):
    """Call your function. NotImplementedError marks the check as not started."""
    try:
        value = fn(*args, **kwargs)
    except NotImplementedError as e:
        result.started = False
        result.passed = False
        raise NotStarted from e
    except Exception:
        result.passed = False
        tb = traceback.format_exc().strip().splitlines()
        result.details.append(t("check.raised", fn=getattr(fn, "__name__", "?"), error=tb[-1]))
        result.details.extend("    " + line for line in tb[-5:-1])
        return None
    if value is None and not none_ok:
        result.fail(t("check.none", fn=getattr(fn, "__name__", "?")))
    return value


def reference(milestone_id: str):
    """A milestone's reference solution, to stand in for the parts other milestones build."""
    import importlib.util

    from .. import ROOT
    from ..milestones import MILESTONES

    path = ROOT / MILESTONES[milestone_id].reference
    spec = importlib.util.spec_from_file_location(f"groundstop_reference_m{milestone_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tally(result: Result, right: int, total: int, unit: dict[str, str]) -> None:
    """Score line; a check passes only when every answer is right."""
    result.score = f"{right}/{total} {unit[lang()]}"
    if right < total:
        result.passed = False


def _color(code: str, text: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def report(milestone: Milestone, results: list[Result]) -> bool:
    lg = lang()
    print()
    print(_color("1", t("check.title", id=milestone.id, title=milestone.title[lg])))
    print(_color("2", t("check.instructions", url=milestone.url(lg))))
    print()
    width = max(len(r.name[lg]) for r in results) + 2
    for r in results:
        if not r.started:
            mark, state = _color("2", "·"), _color("2", t("check.not_started"))
        elif r.passed:
            mark, state = _color("32", "✓"), r.score
        else:
            mark, state = _color("31", "✗"), r.score
        print(f"  {mark} {r.name[lg].ljust(width)}{state}")
        if r.started:
            shown = r.details[:MAX_DETAILS]
            for line in shown:
                print(_color("2", f"      {line}"))
            if len(r.details) > len(shown):
                print(_color("2", "      " + t("check.more", n=len(r.details) - len(shown))))
        for line in r.notes:
            print(f"      {line}")
        if r.started and not r.passed and r.lesson:
            print(_color("36", "      " + t("check.read", title=r.lesson.title(lg), url=r.lesson.url(lg))))
    passed = sum(r.passed for r in results)
    print()
    print(_color("1;32" if passed == len(results) else "1", t("check.summary", passed=passed, total=len(results))))
    if passed == len(results):
        print(t("check.done"))
    print()
    return passed == len(results)
