#!/usr/bin/env python3
"""shakhactl -- the Shakha control CLI.

    python shakhactl.py dashboard          start the learning dashboard
    python shakhactl.py list               list every scenario
    python shakhactl.py start <id>         build a scenario sandbox on disk
    python shakhactl.py verify <id>        grade the sandbox as it stands
    python shakhactl.py reset <id>         rebuild the sandbox from scratch
    python shakhactl.py clean              delete every sandbox
    python shakhactl.py doctor             check the toolchain
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from server.catalog import CATEGORY_LABELS, Catalog          # noqa: E402
from server.gitsandbox import Sandbox, _force_rm             # noqa: E402
from server.grader import grade                              # noqa: E402

SCENARIOS_DIR = ROOT / "scenarios"
WORKSPACES_DIR = ROOT / "workspaces"


def _catalog() -> Catalog:
    return Catalog(SCENARIOS_DIR)


def _need(catalog: Catalog, scenario_id: str):
    scenario = catalog.get(scenario_id)
    if not scenario:
        sys.exit("unknown scenario: %s (try: shakhactl.py list)" % scenario_id)
    return scenario


def cmd_dashboard(args):
    from server.app import serve
    serve(port=args.port, open_browser=not args.no_open)


def cmd_list(args):
    catalog = _catalog()
    current = None
    for scenario in catalog.all():
        category = scenario.get("category")
        if category != current:
            current = category
            print("\n%s" % CATEGORY_LABELS.get(category, category).upper())
        print("  %-42s %-12s %s" % (scenario["id"], scenario.get("level", ""),
                                    scenario.get("title", "")))
    print("\n%d scenarios" % len(catalog.all()))


def cmd_start(args):
    catalog = _catalog()
    scenario = _need(catalog, args.id)
    sandbox = Sandbox(WORKSPACES_DIR, scenario["id"])
    for step in sandbox.build(scenario.get("setup")):
        if step["code"] != 0:
            print("  setup warning: %s -> %s" % (step["cmd"], step["stderr"]))
    print("sandbox ready: %s" % sandbox.repo)


def cmd_reset(args):
    cmd_start(args)


def cmd_verify(args):
    catalog = _catalog()
    scenario = _need(catalog, args.id)
    sandbox = Sandbox(WORKSPACES_DIR, scenario["id"])
    if not sandbox.exists():
        sys.exit("sandbox not built yet: shakhactl.py start %s" % scenario["id"])
    report = grade(sandbox, scenario.get("verify"))
    for check in report["checks"]:
        print("  [%s] %s" % ("PASS" if check["ok"] else "FAIL", check["label"]))
        if not check["ok"]:
            print("        %s" % (check["reason"] or ""))
            if check["hint"]:
                print("        hint: %s" % check["hint"])
    print("%d/%d checks passed -- %s" % (report["passed"], report["total"],
                                         "SOLVED" if report["solved"] else "not solved yet"))
    sys.exit(0 if report["solved"] else 1)


def cmd_clean(args):
    if WORKSPACES_DIR.exists():
        for child in WORKSPACES_DIR.iterdir():
            if child.is_dir():
                _force_rm(child)
    print("workspaces cleared")


def cmd_doctor(args):
    ok = True
    git = shutil.which("git")
    print("python  : %s" % sys.version.split()[0])
    print("git     : %s" % (git or "NOT FOUND"))
    if git:
        version = subprocess.run([git, "--version"], capture_output=True, text=True)
        print("          %s" % version.stdout.strip())
    else:
        ok = False
    catalog = _catalog()
    broken = [s["id"] for s in catalog.all() if s.get("broken")]
    print("scenarios: %d loaded, %d broken" % (len(catalog.all()), len(broken)))
    for scenario_id in broken:
        print("           broken: %s" % scenario_id)
    print("workspaces: %s" % WORKSPACES_DIR)
    sys.exit(0 if ok and not broken else 1)


def main():
    parser = argparse.ArgumentParser(prog="shakhactl", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    dash = subparsers.add_parser("dashboard", help="start the learning dashboard")
    dash.add_argument("--port", type=int, default=4100)
    dash.add_argument("--no-open", action="store_true", help="do not open a browser")
    dash.set_defaults(func=cmd_dashboard)

    subparsers.add_parser("list", help="list scenarios").set_defaults(func=cmd_list)

    for name, func, helptext in (("start", cmd_start, "build a scenario sandbox"),
                                 ("reset", cmd_reset, "rebuild a scenario sandbox"),
                                 ("verify", cmd_verify, "grade a scenario sandbox")):
        sub = subparsers.add_parser(name, help=helptext)
        sub.add_argument("id")
        sub.set_defaults(func=func)

    subparsers.add_parser("clean", help="delete every sandbox").set_defaults(func=cmd_clean)
    subparsers.add_parser("doctor", help="check the toolchain").set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
