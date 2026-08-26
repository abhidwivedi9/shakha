"""Real git execution inside a guarded sandbox.

Every command the dashboard runs ends up here. There is no simulation layer:
git is the actual git binary and the repo is an actual repo on disk. The only
thing this module adds is a hard boundary around WHERE that is allowed to
happen, plus a structured read of repo state for the visualiser.
"""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import time
from pathlib import Path

# Commands a learner may type into the free terminal. Anything else is refused
# with a hint rather than executed -- this is a teaching sandbox, not a shell.
ALLOWED_BINARIES = {"git", "ls", "cat", "pwd", "echo"}

# Identity deliberately does NOT live here. Environment variables outrank
# config, which would make `git config user.email` unteachable -- so the
# learner's identity is seeded into the sandbox's own global config instead.
GIT_ENV = {
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
    "LC_ALL": "C",
}

SEED_GLOBAL_CONFIG = """[user]
\tname = Learner
\temail = learner@shakha.local
[init]
\tdefaultBranch = main
[core]
\tautocrlf = false
[advice]
\tdetachedHead = false
"""

# A second person, for scenarios that need two humans. Here env vars are exactly
# what we want: they override config for this one command and nothing else.
TEAMMATE_ENV = dict(
    GIT_ENV,
    GIT_AUTHOR_NAME="Priya", GIT_AUTHOR_EMAIL="priya@shakha.local",
    GIT_COMMITTER_NAME="Priya", GIT_COMMITTER_EMAIL="priya@shakha.local",
)

US = "\x1f"  # unit separator, used to make git output unambiguously parseable


class SandboxError(Exception):
    pass


def _force_rm(path: Path) -> None:
    """rmtree that survives git read-only object files on Windows."""
    def on_error(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if path.exists():
        try:
            shutil.rmtree(path, onexc=on_error)
        except TypeError:  # Python < 3.12
            shutil.rmtree(path, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))


class Sandbox:
    """One scenario disposable world: a working repo and an optional origin."""

    def __init__(self, workspaces_root: Path, scenario_id: str):
        self.root = Path(workspaces_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.scenario_id = scenario_id
        self.base = (self.root / scenario_id).resolve()
        self._guard(self.base)

    # ---- safety -----------------------------------------------------------

    def _guard(self, path: Path) -> Path:
        """Refuse to touch anything outside workspaces/. Belt and braces."""
        resolved = Path(path).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise SandboxError("refusing to operate outside the sandbox: %s" % resolved)
        return resolved

    # ---- locations --------------------------------------------------------

    @property
    def repo(self) -> Path:
        return self.base / "repo"

    @property
    def origin(self) -> Path:
        return self.base / "origin.git"

    @property
    def teammate(self) -> Path:
        return self.base / "teammate"

    def exists(self) -> bool:
        return self.repo.exists()

    def resolve_cwd(self, name):
        return {
            "repo": self.repo,
            "origin": self.origin,
            "teammate": self.teammate,
        }.get(name or "repo", self.repo)

    # ---- execution --------------------------------------------------------

    def run(self, command, cwd="repo", env_extra=None, check=False) -> dict:
        """Run one command. `command` is a string or argv list. Never uses a shell."""
        argv = shlex.split(command) if isinstance(command, str) else [str(a) for a in command]
        if not argv:
            raise SandboxError("empty command")

        workdir = self._guard(self.resolve_cwd(cwd))
        workdir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env.update(GIT_ENV)
        # Each sandbox gets its own throwaway "global" config, so scenarios can
        # teach `git config --global` without ever reaching the real ~/.gitconfig.
        fake_home = self.base / "home"
        fake_home.mkdir(parents=True, exist_ok=True)
        global_config = fake_home / ".gitconfig"
        if not global_config.exists():
            with open(global_config, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(SEED_GLOBAL_CONFIG)
        env["GIT_CONFIG_GLOBAL"] = str(global_config)
        env["HOME"] = str(fake_home)
        if env_extra:
            env.update(env_extra)

        started = time.time()
        try:
            # stdin is closed deliberately: some commands (shortlog, hash-object)
            # fall back to reading stdin when it is not a terminal, and would
            # otherwise block the dashboard forever.
            proc = subprocess.run(argv, cwd=str(workdir), env=env, capture_output=True,
                                  stdin=subprocess.DEVNULL, text=True, timeout=30,
                                  errors="replace")
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        except FileNotFoundError:
            out, err, code = "", "%s: command not found" % argv[0], 127
        except subprocess.TimeoutExpired:
            out, err, code = "", "command timed out after 30s", 124

        return {
            "cmd": " ".join(argv),
            "cwd": cwd or "repo",
            "stdout": (out or "").rstrip("\n"),
            "stderr": (err or "").rstrip("\n"),
            "code": code,
            "ms": int((time.time() - started) * 1000),
        }

    def run_user(self, command: str, cwd="repo") -> dict:
        """Run a command the learner typed. Same engine, stricter door policy."""
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return self._refuse(command, cwd, "could not parse that command: %s" % exc, 2)
        if not argv:
            return {"cmd": "", "cwd": cwd or "repo", "stdout": "", "stderr": "", "code": 0, "ms": 0}
        if argv[0] not in ALLOWED_BINARIES:
            return self._refuse(
                command, cwd,
                "'%s' is not available in the sandbox. Allowed: %s."
                % (argv[0], ", ".join(sorted(ALLOWED_BINARIES))), 126)
        if argv[0] == "pwd":
            return {"cmd": command, "cwd": cwd or "repo", "stdout": str(self.resolve_cwd(cwd)),
                    "stderr": "", "code": 0, "ms": 0}
        return self.run(argv, cwd=cwd)

    @staticmethod
    def _refuse(command, cwd, message, code) -> dict:
        return {"cmd": command, "cwd": cwd or "repo", "stdout": "", "stderr": message,
                "code": code, "ms": 0}

    def git(self, args: str, cwd="repo", **kw) -> dict:
        return self.run("git " + args, cwd=cwd, **kw)

    def _out(self, args: str, cwd="repo") -> str:
        result = self.git(args, cwd=cwd)
        return result["stdout"] if result["code"] == 0 else ""

    # ---- files ------------------------------------------------------------

    def read_file(self, path: str, cwd="repo") -> dict:
        target = self._guard(self.resolve_cwd(cwd) / path)
        if not target.is_file():
            raise SandboxError("no such file: %s" % path)
        try:
            return {"path": path, "cwd": cwd, "content": target.read_text(encoding="utf-8"),
                    "binary": False}
        except UnicodeDecodeError:
            return {"path": path, "cwd": cwd, "content": "", "binary": True}

    def write_file(self, path: str, content: str, cwd="repo") -> dict:
        target = self._guard(self.resolve_cwd(cwd) / path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        return {"path": path, "cwd": cwd, "bytes": len(content)}

    def list_files(self, cwd="repo") -> list:
        """Every tracked-or-not file in the working tree, minus .git."""
        base = self._guard(self.resolve_cwd(cwd))
        if not base.exists():
            return []
        found = []
        for entry in sorted(base.rglob("*")):
            if ".git" in entry.parts or not entry.is_file():
                continue
            found.append(str(entry.relative_to(base)).replace("\\", "/"))
            if len(found) >= 60:
                break
        return found

    def apply_actions(self, actions) -> list:
        """Run a declarative action list (same schema the setup block uses)."""
        log = []
        for action in actions or []:
            log.extend(self._apply(action))
        return log

    # ---- lifecycle --------------------------------------------------------

    def destroy(self) -> None:
        _force_rm(self._guard(self.base))

    def build(self, setup_actions) -> list:
        """Wipe and re-create the scenario world from its declarative setup."""
        self.destroy()
        self.repo.mkdir(parents=True, exist_ok=True)
        log = []
        for action in setup_actions or []:
            log.extend(self._apply(action))
        return log

    def _apply(self, action: dict) -> list:
        cwd = action.get("cwd", "repo")
        env = dict(TEAMMATE_ENV) if action.get("as") == "teammate" else None
        if action.get("env"):
            # Lets a scenario drive things like GIT_SEQUENCE_EDITOR, which is how
            # an interactive rebase can be demonstrated without a blocking editor.
            env = dict(env or GIT_ENV, **action["env"])

        if "run" in action:
            return [self.run(action["run"], cwd=cwd, env_extra=env)]

        if "write" in action:
            spec = action["write"]
            target = self._guard(self.resolve_cwd(cwd) / spec["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            content = spec.get("content", "")
            if content and not content.endswith("\n"):
                content += "\n"
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            return [self._note("write " + spec["path"], cwd)]

        if "delete" in action:
            target = self._guard(self.resolve_cwd(cwd) / action["delete"])
            if target.is_dir():
                _force_rm(target)
            elif target.exists():
                target.unlink()
            return [self._note("delete " + action["delete"], cwd)]

        if "commit" in action:
            spec = action["commit"]
            steps = [self.run(["git", "add"] + shlex.split(spec.get("add", "-A")),
                              cwd=cwd, env_extra=env)]
            steps.append(self.run(["git", "commit", "-m", spec["message"]],
                                  cwd=cwd, env_extra=env))
            return steps

        if action.get("init_origin"):
            self.origin.mkdir(parents=True, exist_ok=True)
            branch = action.get("push_branch", "main")
            # -b matters: without it the bare repo's HEAD points at master, and
            # every clone of it checks out nothing.
            return [
                self.run("git init --bare -q -b %s" % branch, cwd="origin"),
                self.run(["git", "remote", "add", "origin", str(self.origin)], cwd="repo"),
                self.run("git push -q -u origin " + branch, cwd="repo"),
            ]

        if action.get("clone_teammate"):
            return [self.run(["git", "clone", "-q", str(self.origin), str(self.teammate)],
                             cwd="repo")]

        raise SandboxError("unknown setup action: %s" % list(action))

    @staticmethod
    def _note(label: str, cwd: str) -> dict:
        return {"cmd": label, "cwd": cwd, "stdout": "", "stderr": "", "code": 0, "ms": 0}

    # ---- state for the visualiser ----------------------------------------

    def state(self) -> dict:
        if not (self.repo / ".git").exists():
            return {"initialised": False, "path": str(self.repo),
                    "files": self.list_files() if self.repo.exists() else []}

        return {
            "initialised": True,
            "path": str(self.repo),
            "head": self._head(),
            "commits": self._commits(),
            "branches": self._branches(),
            "tags": self._tags(),
            "remotes": self._remotes(),
            "status": self._status(),
            "stashes": self._stashes(),
            "reflog": self._reflog(),
            "operation": self._operation(),
            "files": self.list_files(),
        }

    def _head(self) -> dict:
        branch = self._out("symbolic-ref --quiet --short HEAD")
        sha = self._out("rev-parse --short HEAD")
        return {"branch": branch or None, "sha": sha or None,
                "detached": (not branch) and bool(sha)}

    def _commits(self, limit: int = 80) -> list:
        fmt = US.join(["%H", "%h", "%P", "%s", "%an", "%ar"])
        raw = self._out("log --all --date-order --pretty=%s -n %d" % (fmt, limit))
        commits = []
        for line in raw.splitlines():
            parts = line.split(US)
            if len(parts) != 6:
                continue
            sha, short, parents, subject, author, when = parts
            commits.append({"sha": sha, "short": short, "subject": subject, "author": author,
                            "when": when, "parents": parents.split() if parents.strip() else []})
        return commits

    def _for_each_ref(self, fields, pattern) -> list:
        fmt = "%1f".join(fields)
        out = self._out("for-each-ref --format=%s %s" % (shlex.quote(fmt), pattern))
        rows = []
        for line in out.splitlines():
            parts = line.split(US)
            parts += [""] * (len(fields) - len(parts))
            rows.append(parts)
        return rows

    def _branches(self) -> list:
        head = self._head().get("branch")
        branches = []
        for name, sha, upstream, track in self._for_each_ref(
                ["%(refname:short)", "%(objectname:short)", "%(upstream:short)",
                 "%(upstream:track)"], "refs/heads"):
            branches.append({"name": name, "sha": sha, "upstream": upstream or None,
                             "track": track.strip("[]") or None, "remote": False,
                             "current": name == head})
        for name, sha in self._for_each_ref(
                ["%(refname:short)", "%(objectname:short)"], "refs/remotes"):
            if not name.endswith("/HEAD"):
                branches.append({"name": name, "sha": sha, "remote": True, "upstream": None,
                                 "track": None, "current": False})
        return branches

    def _tags(self) -> list:
        return [{"name": n, "sha": s, "annotated": t == "tag"}
                for n, s, t in self._for_each_ref(
                    ["%(refname:short)", "%(objectname:short)", "%(objecttype)"], "refs/tags")]

    def _remotes(self) -> list:
        seen, remotes = set(), []
        for line in self._out("remote -v").splitlines():
            bits = line.split()
            if len(bits) >= 2 and bits[0] not in seen:
                seen.add(bits[0])
                remotes.append({"name": bits[0], "url": bits[1]})
        return remotes

    def _status(self) -> dict:
        out = self._out("status --porcelain=v1 --untracked-files=all")
        staged, unstaged, untracked, conflicted = [], [], [], []
        for line in out.splitlines():
            if len(line) < 4:
                continue
            x, y, path = line[0], line[1], line[3:]
            if "U" in (x, y) or (x, y) in (("A", "A"), ("D", "D")):
                conflicted.append(path)
                continue
            if (x, y) == ("?", "?"):
                untracked.append(path)
                continue
            if x != " ":
                staged.append({"path": path, "code": x})
            if y != " ":
                unstaged.append({"path": path, "code": y})
        return {"staged": staged, "unstaged": unstaged, "untracked": untracked,
                "conflicted": conflicted,
                "clean": not (staged or unstaged or untracked or conflicted)}

    def _stashes(self) -> list:
        stashes = []
        for line in self._out("stash list --pretty=%%gd%s%%s" % US).splitlines():
            parts = line.split(US)
            if len(parts) == 2:
                stashes.append({"ref": parts[0], "subject": parts[1]})
        return stashes

    def _reflog(self, limit: int = 15) -> list:
        entries = []
        fmt = US.join(["%h", "%gd", "%gs"])
        for line in self._out("reflog --pretty=%s -n %d" % (fmt, limit)).splitlines():
            parts = line.split(US)
            if len(parts) == 3:
                entries.append({"sha": parts[0], "ref": parts[1], "what": parts[2]})
        return entries

    def _operation(self):
        """Surface mid-operation states -- the ones that scare people."""
        gitdir = self.repo / ".git"
        markers = (("MERGE_HEAD", "merging"), ("rebase-merge", "rebasing"),
                   ("rebase-apply", "rebasing"), ("CHERRY_PICK_HEAD", "cherry-picking"),
                   ("REVERT_HEAD", "reverting"), ("BISECT_LOG", "bisecting"))
        for marker, label in markers:
            if (gitdir / marker).exists():
                return label
        return None
