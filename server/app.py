"""Shakha dashboard server: stdlib only, no build step, no dependencies.

Serves web/ as static files and exposes a small JSON API. Every API call that
changes anything runs real git in the scenario sandbox.
"""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .catalog import Catalog
from .gitsandbox import Sandbox, SandboxError
from .grader import grade

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
SCENARIOS_DIR = ROOT / "scenarios"
WORKSPACES_DIR = ROOT / "workspaces"
PROGRESS_FILE = ROOT / "progress.json"

_lock = threading.Lock()


# ---------------------------------------------------------------- progress

def load_progress() -> dict:
    if PROGRESS_FILE.is_file():
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass
    return {"scenarios": {}}


def save_progress(progress: dict) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as handle:
        json.dump(progress, handle, indent=2)


def record(scenario_id: str, **fields) -> dict:
    with _lock:
        progress = load_progress()
        entry = progress["scenarios"].setdefault(
            scenario_id, {"started": False, "solved": False, "commands": 0, "attempts": 0})
        for key, value in fields.items():
            if key == "commands":
                entry["commands"] = entry.get("commands", 0) + value
            elif key == "attempts":
                entry["attempts"] = entry.get("attempts", 0) + value
            elif key == "solved":
                entry["solved"] = entry.get("solved", False) or value
            else:
                entry[key] = value
        save_progress(progress)
        return entry


# ---------------------------------------------------------------- handler

class Handler(BaseHTTPRequestHandler):
    server_version = "Shakha/0.1"
    catalog: Catalog = None  # injected by serve()

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" in (args[0] if args else ""):
            return
        return

    # ---- plumbing ------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def json(self, payload, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---- routing -------------------------------------------------------

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api_get(path)
        return self.static(path)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self.json({"error": "not found"}, 404)
        try:
            return self.api_post(path, self.read_json())
        except SandboxError as exc:
            return self.json({"error": str(exc)}, 400)
        except Exception as exc:  # keep the dashboard alive on scenario bugs
            return self.json({"error": "%s: %s" % (type(exc).__name__, exc)}, 500)

    def static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR not in target.parents or not target.is_file():
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        return self._send(200, target.read_bytes(), ctype)

    # ---- API -----------------------------------------------------------

    def _sandbox(self, scenario_id: str) -> Sandbox:
        return Sandbox(WORKSPACES_DIR, scenario_id)

    def api_get(self, path: str):
        parts = [p for p in path.split("/") if p][1:]  # strip 'api'

        if parts == ["catalog"]:
            payload = self.catalog.summary()
            payload["progress"] = load_progress()["scenarios"]
            return self.json(payload)

        if parts == ["progress"]:
            return self.json(load_progress())

        if len(parts) >= 2 and parts[0] == "scenario":
            scenario = self.catalog.get(parts[1])
            if not scenario:
                return self.json({"error": "unknown scenario"}, 404)
            sandbox = self._sandbox(scenario["id"])

            if len(parts) == 2:
                data = {k: v for k, v in scenario.items() if k != "folder"}
                data["progress"] = load_progress()["scenarios"].get(scenario["id"], {})
                data["ready"] = sandbox.exists()
                return self.json(data)

            if parts[2] == "state":
                return self.json({"ready": sandbox.exists(), "state": sandbox.state()})

            if parts[2] == "file":
                query = parse_qs(urlparse(self.path).query)
                path = (query.get("path") or [""])[0]
                cwd = (query.get("cwd") or ["repo"])[0]
                if not path:
                    return self.json({"error": "path is required"}, 400)
                try:
                    return self.json(sandbox.read_file(path, cwd=cwd))
                except SandboxError as exc:
                    return self.json({"error": str(exc)}, 404)

        return self.json({"error": "not found"}, 404)

    def api_post(self, path: str, body: dict):
        parts = [p for p in path.split("/") if p][1:]

        if parts == ["catalog", "reload"]:
            self.catalog.reload()
            return self.json({"ok": True, "total": len(self.catalog.all())})

        if len(parts) == 3 and parts[0] == "scenario":
            scenario = self.catalog.get(parts[1])
            if not scenario:
                return self.json({"error": "unknown scenario"}, 404)
            sandbox = self._sandbox(scenario["id"])
            action = parts[2]

            if action in ("start", "reset"):
                log = sandbox.build(scenario.get("setup"))
                record(scenario["id"], started=True)
                if action == "reset":
                    with _lock:
                        progress = load_progress()
                        entry = progress["scenarios"].get(scenario["id"])
                        if entry:
                            entry["solved"] = False
                        save_progress(progress)
                return self.json({"ok": True, "setup_log": log, "state": sandbox.state()})

            if action == "run":
                if not sandbox.exists():
                    sandbox.build(scenario.get("setup"))
                    record(scenario["id"], started=True)
                cwd = body.get("cwd", "repo")
                if "step" in body:
                    index = int(body["step"])
                    steps = scenario.get("steps", [])
                    if not 0 <= index < len(steps):
                        return self.json({"error": "no such step"}, 400)
                    step = steps[index]
                    # A step may edit files as well as run commands -- editing is
                    # what a real conflict resolution actually is.
                    results = sandbox.apply_actions(step.get("actions"))
                    results += [sandbox.run(cmd, cwd=step.get("cwd", cwd))
                                for cmd in _step_commands(step)]
                else:
                    command = (body.get("command") or "").strip()
                    if not command:
                        return self.json({"error": "empty command"}, 400)
                    results = [sandbox.run_user(command, cwd=cwd)]

                record(scenario["id"], commands=len(results))
                payload = {"results": results, "state": sandbox.state()}
                if "step" in body:
                    step = scenario["steps"][int(body["step"])]
                    if step.get("verify"):
                        payload["step_grade"] = grade(sandbox, step["verify"])
                return self.json(payload)

            if action == "verify":
                report = grade(sandbox, scenario.get("verify"))
                record(scenario["id"], attempts=1, solved=report["solved"])
                report["state"] = sandbox.state()
                return self.json(report)

            if action == "file":
                path = (body.get("path") or "").strip()
                if not path:
                    return self.json({"error": "path is required"}, 400)
                sandbox.write_file(path, body.get("content", ""), cwd=body.get("cwd", "repo"))
                record(scenario["id"], commands=1)
                return self.json({"ok": True, "state": sandbox.state()})

            if action == "destroy":
                sandbox.destroy()
                return self.json({"ok": True})

        return self.json({"error": "not found"}, 404)


def _step_commands(step: dict) -> list:
    """A step may carry one command or a short sequence."""
    if step.get("commands"):
        return list(step["commands"])
    if step.get("run"):
        return [step["run"]]
    return []


def serve(port: int = 4100, open_browser: bool = True):
    Handler.catalog = Catalog(SCENARIOS_DIR)
    WORKSPACES_DIR.mkdir(exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d" % port
    print("Shakha dashboard -> %s" % url)
    print("%d scenarios loaded. Ctrl-C to stop." % len(Handler.catalog.all()))
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
