"""Shakha dashboard server: stdlib only, no build step, no dependencies.

Serves web/ as static files and exposes a small JSON API. Every API call that
changes anything runs real git in the scenario sandbox.
"""

from __future__ import annotations

import hmac
import json
import secrets
import mimetypes
import shutil
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .catalog import Catalog
from .gitsandbox import Sandbox, SandboxError, _force_rm
from .grader import grade

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
SCENARIOS_DIR = ROOT / "scenarios"
WORKSPACES_DIR = ROOT / "workspaces"
PROGRESS_FILE = ROOT / "progress.json"
SESSIONS_DIR = ROOT / "sessions"        # one progress file per visitor, multi-user mode
SESSION_MAX_AGE = 24 * 3600             # a visitor's sandboxes live a day, then are reaped

_lock = threading.Lock()


# ---------------------------------------------------------------- progress

def load_progress(store: Path = None) -> dict:
    store = store or PROGRESS_FILE
    if store.is_file():
        try:
            with open(store, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass
    return {"scenarios": {}}


def save_progress(progress: dict, store: Path = None) -> None:
    store = store or PROGRESS_FILE
    store.parent.mkdir(parents=True, exist_ok=True)
    with open(store, "w", encoding="utf-8") as handle:
        json.dump(progress, handle, indent=2)


def record(scenario_id: str, store: Path = None, **fields) -> dict:
    with _lock:
        progress = load_progress(store)
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
        save_progress(progress, store)
        return entry


# ---------------------------------------------------------------- handler

LOCKED_PAGE = """<!doctype html><meta charset="utf-8">
<title>Shakha — key required</title>
<body style="margin:0;display:grid;place-items:center;height:100vh;background:#0f1216;
             color:#9aa7b6;font:15px/1.6 system-ui,sans-serif;text-align:center">
<div><p style="color:#e6edf3;font-size:18px;margin:0 0 6px">This dashboard is locked.</p>
<p style="margin:0">Open the full link you were given &mdash; the one ending in
<code style="color:#58a6ff">?k=&hellip;</code>.</p></div></body>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Shakha/0.1"
    catalog: Catalog = None  # injected by serve()
    key: str = None          # injected by serve(); None means no gate at all
    sessions: bool = False   # injected by serve(); True = a sandbox set per visitor
    session: str = None

    # ---- one visitor, one set of repositories --------------------------

    def claim_session(self) -> None:
        """Single-user mode shares one workspace, as it always has. Multi-user
        mode hands every browser its own, so two people on the same scenario
        never end up committing into the same repository."""
        if not self.sessions:
            return
        for crumb in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = crumb.strip().partition("=")
            # the id becomes a directory name, so only ever trust plain hex
            if name == "shakha_session" and len(value) == 16 and value.isalnum():
                self.session = value
                return
        self.session = secrets.token_hex(8)
        self._session_cookie = ("shakha_session=%s; Path=/; Max-Age=%d; SameSite=Lax; "
                                "HttpOnly" % (self.session, SESSION_MAX_AGE))

    @property
    def workspaces_dir(self) -> Path:
        return WORKSPACES_DIR / self.session if self.session else WORKSPACES_DIR

    @property
    def progress_store(self) -> Path:
        return SESSIONS_DIR / ("%s.json" % self.session) if self.session else PROGRESS_FILE

    # ---- the key gate --------------------------------------------------

    def _supplied_key(self):
        """The key from the query string, then the cookie, then a header."""
        query = parse_qs(urlparse(self.path).query).get("k")
        if query:
            return query[0]
        for crumb in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = crumb.strip().partition("=")
            if name == "shakha_key":
                return value
        return self.headers.get("X-Shakha-Key")

    def authorised(self) -> bool:
        if not self.key:
            return True
        supplied = self._supplied_key()
        # compare_digest so a wrong key cannot be found one character at a time
        return supplied is not None and hmac.compare_digest(str(supplied), self.key)

    def locked(self):
        return self._send(403, LOCKED_PAGE.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" in (args[0] if args else ""):
            return
        return

    # ---- plumbing ------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str, extra: dict = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        if getattr(self, "_session_cookie", None):
            self.send_header("Set-Cookie", self._session_cookie)
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
        if not self.authorised():
            return self.locked()
        self.claim_session()
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self.api_get(path)
        if self.key and parse_qs(parsed.query).get("k"):
            # spend the key once: park it in a cookie and drop it from the address
            # bar, so a screenshot or a shoulder does not hand it on
            return self._send(302, b"", "text/plain", {
                "Location": path or "/",
                "Set-Cookie": "shakha_key=%s; Path=/; Max-Age=604800; SameSite=Lax; HttpOnly"
                              % self.key,
            })
        return self.static(path)

    def do_POST(self):  # noqa: N802
        if not self.authorised():
            return self.json({"error": "forbidden"}, 403)
        self.claim_session()
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
        return Sandbox(self.workspaces_dir, scenario_id)

    def api_get(self, path: str):
        parts = [p for p in path.split("/") if p][1:]  # strip 'api'

        if parts == ["catalog"]:
            payload = self.catalog.summary()
            payload["progress"] = load_progress(self.progress_store)["scenarios"]
            return self.json(payload)

        if parts == ["progress"]:
            return self.json(load_progress(self.progress_store))

        if len(parts) >= 2 and parts[0] == "scenario":
            scenario = self.catalog.get(parts[1])
            if not scenario:
                return self.json({"error": "unknown scenario"}, 404)
            sandbox = self._sandbox(scenario["id"])

            if len(parts) == 2:
                data = {k: v for k, v in scenario.items() if k != "folder"}
                data["progress"] = load_progress(self.progress_store)["scenarios"].get(scenario["id"], {})
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
                record(scenario["id"], self.progress_store, started=True)
                if action == "reset":
                    with _lock:
                        progress = load_progress(self.progress_store)
                        entry = progress["scenarios"].get(scenario["id"])
                        if entry:
                            entry["solved"] = False
                        save_progress(progress, self.progress_store)
                return self.json({"ok": True, "setup_log": log, "state": sandbox.state()})

            if action == "run":
                if not sandbox.exists():
                    sandbox.build(scenario.get("setup"))
                    record(scenario["id"], self.progress_store, started=True)
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

                record(scenario["id"], self.progress_store, commands=len(results))
                payload = {"results": results, "state": sandbox.state()}
                if "step" in body:
                    step = scenario["steps"][int(body["step"])]
                    if step.get("verify"):
                        payload["step_grade"] = grade(sandbox, step["verify"])
                return self.json(payload)

            if action == "verify":
                report = grade(sandbox, scenario.get("verify"))
                record(scenario["id"], self.progress_store, attempts=1, solved=report["solved"])
                report["state"] = sandbox.state()
                return self.json(report)

            if action == "file":
                path = (body.get("path") or "").strip()
                if not path:
                    return self.json({"error": "path is required"}, 400)
                sandbox.write_file(path, body.get("content", ""), cwd=body.get("cwd", "repo"))
                record(scenario["id"], self.progress_store, commands=1)
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


def reap_sessions(max_age: int = SESSION_MAX_AGE) -> int:
    """Drop visitors who have gone away.

    Multi-user mode hands every browser its own clones, and a free host's disk is
    small, so a session that has not been touched for a day is deleted outright.
    Nothing of value is lost: sandboxes are rebuilt from the scenario on demand.
    """
    removed = 0
    cutoff = time.time() - max_age
    for parent, is_dir in ((WORKSPACES_DIR, True), (SESSIONS_DIR, False)):
        if not parent.is_dir():
            continue
        for entry in parent.iterdir():
            if entry.is_dir() != is_dir:
                continue
            try:
                if entry.stat().st_mtime >= cutoff:
                    continue
                _force_rm(entry) if is_dir else entry.unlink()
                removed += 1
            except OSError:
                pass                      # a locked sandbox is simply reaped next time
    return removed


def _reaper_loop(interval: int = 1800) -> None:
    while True:
        time.sleep(interval)
        try:
            reap_sessions()
        except Exception:                 # never let housekeeping kill the server
            pass


def lan_addresses() -> list:
    """Best-effort list of addresses this machine can be reached on."""
    found = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # connecting a UDP socket sends nothing; it only asks the OS which
        # interface would carry traffic to the outside world
        sock.connect(("8.8.8.8", 80))
        found.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    return found


def serve(port: int = 4100, open_browser: bool = True, host: str = "127.0.0.1",
          key: str = None, sessions: bool = False):
    Handler.catalog = Catalog(SCENARIOS_DIR)
    Handler.key = key
    Handler.sessions = sessions
    WORKSPACES_DIR.mkdir(exist_ok=True)
    if sessions:
        SESSIONS_DIR.mkdir(exist_ok=True)
        reap_sessions()
        threading.Thread(target=_reaper_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    suffix = "/?k=%s" % key if key else ""
    url = "http://127.0.0.1:%d%s" % (port, suffix)
    print("Shakha dashboard -> %s" % url)
    if host not in ("127.0.0.1", "localhost"):
        for address in lan_addresses():
            print("  shared on this network -> http://%s:%d%s" % (address, port, suffix))
        if key:
            print("  the key is part of the link -- without it every request gets a 403.")
        else:
            print("  no key set: anyone who can reach this machine can drive the sandboxes")
            print("  and the terminal. Add --key to lock it. Ctrl-C stops sharing.")
    if sessions:
        print("  multi-user: every browser gets its own sandboxes and its own progress.")
    print("%d scenarios loaded. Ctrl-C to stop." % len(Handler.catalog.all()))
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
