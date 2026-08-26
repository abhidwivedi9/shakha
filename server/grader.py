"""Declarative checks that decide whether a scenario is actually solved.

A check runs a real command in the sandbox and asserts something about its
output or exit code. That means a scenario is graded on the true state of the
repository -- not on which buttons were clicked.
"""

from __future__ import annotations

import re


def _describe(check: dict) -> str:
    if check.get("label"):
        return check["label"]
    for key in ("equals", "contains", "not_contains", "matches"):
        if key in check:
            return "%s -> %s %r" % (check.get("cmd", "?"), key.replace("_", " "), check[key])
    if check.get("empty"):
        return "%s produces no output" % check.get("cmd", "?")
    if check.get("not_empty"):
        return "%s produces output" % check.get("cmd", "?")
    return check.get("cmd", "check")


def run_check(sandbox, check: dict) -> dict:
    result = sandbox.run(check["cmd"], cwd=check.get("cwd", "repo"))
    output = result["stdout"]
    if check.get("include_stderr"):
        output = (output + "\n" + result["stderr"]).strip()
    ok, reason = True, ""

    expected_code = check.get("code")
    if expected_code is not None and result["code"] != expected_code:
        ok, reason = False, "exit code %s, expected %s" % (result["code"], expected_code)
    elif expected_code is None and result["code"] != 0 and not check.get("allow_failure"):
        ok, reason = False, (result["stderr"] or "command failed").splitlines()[0]

    if ok and "equals" in check:
        if output.strip() != str(check["equals"]).strip():
            ok, reason = False, "got %r" % (output.strip()[:120] or "")
    if ok and "contains" in check:
        needles = check["contains"]
        needles = needles if isinstance(needles, list) else [needles]
        missing = [n for n in needles if n not in output]
        if missing:
            ok, reason = False, "missing: %s" % ", ".join(repr(m) for m in missing)
    if ok and "not_contains" in check:
        needles = check["not_contains"]
        needles = needles if isinstance(needles, list) else [needles]
        present = [n for n in needles if n in output]
        if present:
            ok, reason = False, "still present: %s" % ", ".join(repr(p) for p in present)
    if ok and "matches" in check:
        if not re.search(check["matches"], output, re.MULTILINE):
            ok, reason = False, "no match for /%s/" % check["matches"]
    if ok and check.get("empty") and output.strip():
        ok, reason = False, "expected no output, got %r" % output.strip()[:120]
    if ok and check.get("not_empty") and not output.strip():
        ok, reason = False, "expected some output, got nothing"
    if ok and "lines" in check and len(output.splitlines()) != int(check["lines"]):
        ok, reason = False, "%d lines, expected %s" % (len(output.splitlines()), check["lines"])

    return {
        "label": _describe(check),
        "cmd": result["cmd"],
        "ok": ok,
        "reason": reason,
        "hint": check.get("hint", ""),
        "output": output[:800],
    }


def grade(sandbox, checks) -> dict:
    results = [run_check(sandbox, check) for check in (checks or [])]
    passed = sum(1 for r in results if r["ok"])
    return {
        "checks": results,
        "passed": passed,
        "total": len(results),
        "solved": bool(results) and passed == len(results),
    }
