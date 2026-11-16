"""`ground-stop`: replay a night through a mesh and read the scoreboard.

ground-stop nights                     the nights in this repo
ground-stop show p1                    what happens on a night (the practice nights tell you in advance)
ground-stop replay                     replay p1 with the naive mesh; logs go to runs/p1/
ground-stop replay s2 --mesh mine      ...another night, with your mesh (src/groundstop/mine/mesh.py)
ground-stop replay --rebooking mine    ...with your rebooking agent from milestone 2
ground-stop --lang en replay           in English (or set GROUND_STOP_LANG=en)
ground-stop trace PX-48187 --mesh mine one passenger's trace, through your mesh's tracer (milestone 4)
ground-stop check 1                    run milestone 1's checks on your code (--reference: on the reference)
ground-stop use-reference 1            swap your file for the reference (yours is kept as *.mine.py; --undo)
ground-stop generate --pack standard   rebuild a pack of nights from its seeds
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import NIGHTS, ROOT, RUNS
from .i18n import LANGS, num, set_lang, t
from .util import hhmm


def find_night(night_id: str) -> Path:
    for path in sorted(NIGHTS.glob(f"*/{night_id}.json")):
        return path
    sys.exit(t("cli.no_night", night=night_id))


def cmd_nights(args) -> None:
    from .night.model import load

    print(t("cli.nights.header"))
    for pack in ("practice", "standard", "final"):
        for path in sorted((NIGHTS / pack).glob("*.json")):
            n = load(path)
            print(
                f"{n.id:<6} {t(f'pack.{pack}'):<10} {hhmm(n.storm_start):<9} {len(n.cancelled):<7} {num(len(n.passengers))}"
            )


def cmd_show(args) -> None:
    from .night.model import load
    from .night.places import DESTINATIONS

    n = load(find_night(args.night))
    print(t("show.title", night=n.id, pack=t(f"pack.{n.pack}"), start=hhmm(n.storm_start)))
    print()
    print(t("show.flights"))
    for f in sorted(n.cancelled, key=lambda f: f.dep):
        pax = sum(1 for p in n.passengers if p.flight == f.id)
        city = DESTINATIONS[f.dest][0]
        print(
            f"  {f.id:<6} {hhmm(f.dep)}  {f.dest} {city:<24} {f.aircraft:<5} {t('show.pax', pax=pax):<16} {t('show.cancel_at', at=hhmm(f.cancel_at))}"
        )
    extras = [f for f in n.flights if f.kind == "extra"]
    print()
    print(t("show.extras", count=len(extras), crews=len(n.crews)))
    print(t("show.hotels", rooms=num(sum(h.rooms for h in n.hotels)), care=num(n.airside_care)))
    print()
    if n.pack == "practice":
        print(t("show.events"))
        for e in n.events:
            data = dict(e.data)
            if "down_for" in data:
                data["minutes"] = data["down_for"] // 60
            print(f"  {hhmm(e.at)}  {t(f'event.{e.type}', **data)}")
    else:
        print(t("show.hidden"))


def cmd_replay(args) -> None:
    from .mesh import build
    from .night.model import load
    from .score import mesh_name, render, score, write
    from .sim.engine import Engine

    n = load(find_night(args.night))
    mesh = build("groundstop.mine.mesh" if args.mesh == "mine" else args.mesh)
    agents = {}
    if args.rebooking:
        import importlib

        from .agents.planned import planned_rebooking

        name = "groundstop.mine.m2_a_contract_for_rebooking" if args.rebooking == "mine" else args.rebooking
        agents["rebooking"] = planned_rebooking(importlib.import_module(name))
    print(t("cli.replaying", night=n.id, mesh=mesh_name(mesh.name)))
    engine = Engine(n, mesh, agents=agents).run()
    board = score(engine)
    out = Path(args.out) if args.out else RUNS / n.id
    engine.write_logs(out)
    write(board, out)
    try:
        shown = out.resolve().relative_to(ROOT)
    except ValueError:
        shown = out
    print()
    print(render(board, logs=f"{shown}/"))


def cmd_trace(args) -> None:
    from .mesh import build
    from .night.model import load
    from .sim.engine import Engine
    from .util import clock

    n = load(find_night(args.night))
    mesh = build("groundstop.mine.mesh" if args.mesh == "mine" else args.mesh)
    Engine(n, mesh).run()
    tracer = mesh.tracer
    if not hasattr(tracer, "trace_of"):
        sys.exit(t("cli.no_tracer"))
    tid = tracer.trace_of(args.pax)
    if tid is None:
        sys.exit(t("cli.no_trace", pax=args.pax, night=n.id))
    print(t("cli.trace_title", pax=args.pax, night=n.id, trace=tid))
    for s in tracer.trace(tid):
        handled = clock(s["handled_at"]) if s.get("handled_at") is not None else "-"
        print(f"  {clock(s['sent_at']):>8} → {handled:>8}  {s['sender']} -> {s['to']}  {s['kind']}")
    hop = tracer.slowest_hop(tid)
    if hop.get("agent"):
        print(t("cli.trace_slowest", agent=hop["agent"], minutes=round(hop["seconds"] / 60)))


def _milestone(mid: str):
    from .milestones import MILESTONES

    if mid not in MILESTONES:
        sys.exit(t("cli.no_milestone", id=mid, ids=", ".join(MILESTONES)))
    return MILESTONES[mid]


def cmd_check(args) -> None:
    import importlib
    import importlib.util

    from .checks.core import report

    m = _milestone(args.milestone)
    if args.reference:
        path = ROOT / m.reference
        spec = importlib.util.spec_from_file_location(f"reference_m{m.id}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(m.module)
    checks = importlib.import_module(m.checks)
    print(t("check.running", id=m.id, what=t("check.reference") if args.reference else m.file))
    ok = report(m, checks.run(module))
    sys.exit(0 if ok else 1)


def cmd_use_reference(args) -> None:
    import shutil

    m = _milestone(args.milestone)
    mine, ref = ROOT / m.file, ROOT / m.reference
    backup = mine.with_name(mine.stem + ".mine.py")
    if args.undo:
        if not backup.exists():
            sys.exit(t("cli.no_backup", path=backup.relative_to(ROOT)))
        shutil.move(backup, mine)
        print(t("cli.restored", id=m.id))
        return
    if backup.exists():
        sys.exit(t("cli.backup_exists", path=backup.relative_to(ROOT)))
    shutil.copy(mine, backup)
    shutil.copy(ref, mine)
    print(t("cli.replaced", path=mine.relative_to(ROOT)))


def cmd_generate(args) -> None:
    from .night.generate import generate_pack

    nights = generate_pack(args.pack, NIGHTS)
    print(t("cli.generated", count=len(nights), path=f"nights/{args.pack}/"))


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, a in enumerate(argv):  # the language is needed before the help texts are built
        if a == "--lang" and i + 1 < len(argv) and argv[i + 1] in LANGS:
            set_lang(argv[i + 1])
        elif a.startswith("--lang=") and a.split("=", 1)[1] in LANGS:
            set_lang(a.split("=", 1)[1])

    parser = argparse.ArgumentParser(prog="ground-stop", description=t("cli.description"))
    parser.add_argument("--lang", choices=LANGS, help=t("cli.lang"))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("nights", help=t("cli.help.nights"))
    p.set_defaults(fn=cmd_nights)

    p = sub.add_parser("show", help=t("cli.help.show"))
    p.add_argument("night", nargs="?", default="p1")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("replay", help=t("cli.help.replay"))
    p.add_argument("night", nargs="?", default="p1")
    p.add_argument("--mesh", default="naive", help=t("cli.help.mesh"))
    p.add_argument("--rebooking", help=t("cli.help.rebooking"))
    p.add_argument("--out", help=t("cli.help.out"))
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("trace", help=t("cli.help.trace"))
    p.add_argument("pax")
    p.add_argument("night", nargs="?", default="p1")
    p.add_argument("--mesh", default="mine", help=t("cli.help.mesh"))
    p.set_defaults(fn=cmd_trace)

    p = sub.add_parser("check", help=t("cli.help.check"))
    p.add_argument("milestone")
    p.add_argument("--reference", action="store_true", help=t("cli.help.reference"))
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("use-reference", help=t("cli.help.use_reference"))
    p.add_argument("milestone")
    p.add_argument("--undo", action="store_true", help=t("cli.help.undo"))
    p.set_defaults(fn=cmd_use_reference)

    p = sub.add_parser("generate", help=t("cli.help.generate"))
    p.add_argument("--pack", required=True, choices=["practice", "standard", "final"])
    p.set_defaults(fn=cmd_generate)

    args = parser.parse_args(argv)
    args.fn(args)
