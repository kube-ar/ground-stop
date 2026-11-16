"""Milestone 2, a contract for rebooking: the rebooking agent is yours now. Make it one others can rely on.

Today one model call per passenger reads the case, picks a flight, checks the fare rules, books
the seat and tells four other agents. Now and then it skips a step or books the wrong city. You
split that call into a plan of small steps, most of them plain code, run the plan while writing
down what each step did, check the run against the plan, and publish a contract other teams can
call it by.

- The steps you can use, and what each takes: `groundstop.plans.STEPS`.
- The plan format, the parameter sources and `only_if`: the docstring of `groundstop.plans`.
- Check: `uv run ground-stop check 2`. Try it in a night: `uv run ground-stop replay --rebooking mine`.

Instructions: https://kube.ar/agentic-mesh/project/ground-stop/a-contract-for-rebooking (en español: https://kube.ar/es/agentic-mesh/project/ground-stop/a-contract-for-rebooking)
"""

from __future__ import annotations

from typing import Any


def contract() -> dict[str, Any]:
    """What other teams need to call this agent without asking you anything.

    Keys: name, version, owner, purpose, type (one of the four agent types), input and output
    (each a JSON Schema), and limits (a list: what it won't do). The answer to a caller is the
    result of your plan's book_seat step.
    """
    raise NotImplementedError


def plan(request: dict[str, Any]) -> dict[str, Any]:
    """The task plan for one passenger: {"task_id", "agent", "request", "steps": [...]}.

    `request` has only the fields your contract's input declares. Each step: id, run_by (a key
    of STEPS), parameters, after (ids that must finish first) and, if it applies, only_if.
    """
    raise NotImplementedError


def execute(plan: dict[str, Any], tools: Any) -> list[dict[str, Any]]:
    """Run the plan's steps in order with `tools.call(run_by, parameters)`. Return the execution log.

    One entry per step, in the order they ran:
      {"step": "s1", "run_by": "tool:find_flights", "status": "done", "at": tools.now,
       "parameters": {"dest": {"value": "GRU", "from": "request.dest"}}, "result": [...]}
    A step whose only_if isn't met: status "skipped" and a "reason", no parameters.
    A step whose call raises: status "failed" and an "error"; the run stops there.
    A literal parameter is logged with "from": "literal".
    """
    raise NotImplementedError


def conforms(plan: dict[str, Any], log: list[dict[str, Any]]) -> list[str]:
    """Did the run follow the plan? One sentence per problem; an empty list if it did.

    Look for: a planned step missing from the log, a step in the log that isn't in the plan or
    ran twice, a step that ran before one it waits for, a parameter whose value or source isn't
    what the plan says, and a step skipped when its only_if held (or run when it didn't).
    """
    raise NotImplementedError
