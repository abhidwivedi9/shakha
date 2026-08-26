#!/usr/bin/env python3
"""Regression test for the whole catalog.

Builds every scenario, runs its own steps exactly as the dashboard would, then
grades it. A scenario whose steps do not solve it is a broken scenario.

    python tools/test_scenarios.py [scenario-id ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.catalog import Catalog       # noqa: E402
from server.gitsandbox import Sandbox    # noqa: E402
from server.grader import grade          # noqa: E402


def run_scenario(scenario, verbose: bool) -> bool:
    sandbox = Sandbox(ROOT / "workspaces", scenario["id"])
    ok = True

    for entry in sandbox.build(scenario.get("setup")):
        if entry["code"] != 0:
            print("  SETUP FAILED: %s" % entry["cmd"])
            print("    %s" % (entry["stderr"] or entry["stdout"])[:300])
            ok = False

    for index, step in enumerate(scenario.get("steps", [])):
        results = sandbox.apply_actions(step.get("actions"))
        commands = step.get("commands") or ([step["run"]] if step.get("run") else [])
        results += [sandbox.run(c, cwd=step.get("cwd", "repo")) for c in commands]
        if verbose:
            for r in results:
                print("  step %d: %s%s" % (index + 1, r["cmd"][:88],
                                           "" if r["code"] == 0 else "  (exit %d)" % r["code"]))
        if step.get("verify"):
            report = grade(sandbox, step["verify"])
            if not report["solved"]:
                ok = False
                for check in report["checks"]:
                    if not check["ok"]:
                        print("  STEP %d CHECK FAILED: %s -- %s"
                              % (index + 1, check["label"], check["reason"]))

    report = grade(sandbox, scenario.get("verify"))
    status = "SOLVED" if report["solved"] else "NOT SOLVED"
    print("  %d/%d checks -- %s" % (report["passed"], report["total"], status))
    if not report["solved"]:
        ok = False
        for check in report["checks"]:
            if not check["ok"]:
                print("    FAILED: %s -- %s" % (check["label"], check["reason"]))
    return ok


def main() -> int:
    catalog = Catalog(ROOT / "scenarios")
    wanted = sys.argv[1:]
    scenarios = [s for s in catalog.all() if not wanted or s["id"] in wanted]
    if not scenarios:
        print("no scenarios matched")
        return 1

    verbose = bool(wanted)
    failed = []
    for scenario in scenarios:
        print("=" * 72)
        print(scenario["id"])
        if not run_scenario(scenario, verbose):
            failed.append(scenario["id"])

    print("=" * 72)
    print("%d scenarios, %d failed" % (len(scenarios), len(failed)))
    for scenario_id in failed:
        print("  failed: %s" % scenario_id)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
