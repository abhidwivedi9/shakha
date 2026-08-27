# Shakha — context handover

Paste this into a new chat, or just say: **"read `docs/CONTEXT.md` in C:\Users\swarn\project-shakha"**.

---

## What this is

**Shakha** (शाखा, *branch*) — a locally-hosted, dashboard-based learning platform that
teaches git A to Z. Every scenario builds a **real git repository on disk**; the step
buttons run **real `git` commands**; the commit graph is read out of that repository;
the file editor writes real files; and the checks grade the **repo state**, not which
buttons were pressed. **There is no simulation layer anywhere in the project.**

- **Local path:** `C:\Users\swarn\project-shakha`
- **GitHub:** https://github.com/abhidwivedi9/shakha (branch `main`, 27 commits, in sync)
- **Dashboard:** http://127.0.0.1:4100
- **Owner:** abhidwivedi9 / abhidwivedi9@gmail.com
- **Licence:** Apache-2.0
- **Sibling projects:** `C:\Users\swarn\devops-sre-platform` (Abhyas, DevOps/SRE sim,
  `abhyasctl`, dashboard :4000) and `C:\Users\swarn\project-sutra` (Python vault,
  `sutractl`, dashboard :4001). Same house style: Sanskrit name, stdlib-only Python,
  zero build step, a `*ctl` CLI, content as plain folders on disk.

## Run it

```bash
cd C:\Users\swarn\project-shakha
python shakhactl.py dashboard          # http://127.0.0.1:4100
python shakhactl.py dashboard --share  # bind every interface; prints the LAN address
python shakhactl.py dashboard --share --key    # ... and gate it behind a key
```

`--share` (or `--host <addr>`) is the only way the server leaves loopback — the default
is still 127.0.0.1. It prints every address the machine can be reached on, and a warning:
anyone who can open the page can drive the sandboxes and the allow-listed terminal.

`--key [VALUE]` (generated when the value is omitted) gates **every** request — pages,
static assets and API alike. The key arrives as `?k=`, a query param, a `shakha_key`
cookie or an `X-Shakha-Key` header; a page load carrying `?k=` answers 302 and moves it
into the cookie, so the address bar goes clean. Comparison is `hmac.compare_digest`.
Treat the key as the only thing between the internet and a shell sandbox.

`--multi-user` makes Shakha safe to *share*, which is a different problem from `--key`.
Without it every visitor collides in `workspaces/<scenario-id>` and one global
`progress.json`. With it, a `shakha_session` cookie (16 hex chars, validated before it
is ever used as a directory name) routes each browser to `workspaces/<session>/…` and
`sessions/<session>.json`, and a reaper thread deletes sessions idle for 24h. Local
single-user mode is untouched and still uses the original paths.

`Dockerfile` + `docs/DEPLOY.md` cover hosting it publicly. Note the image must carry
`openssh-client` (the signing scenarios cut real signed tags) and that Debian's git is
older than the Windows one — see the gotchas below.

The web UI is responsive. Below 900px `body[data-pane]` shows one pane at a time and a
tab bar switches between them; opening a scenario jumps to the Lesson pane, and the Repo
tab grows a dot when the repository moves while you are looking elsewhere. Above 900px
nothing changed — same three-column grid, tab bar hidden.

Requires only **Python 3.9+ and git**. No pip install, no npm, no build step.

CLI: `dashboard` · `list` · `path` · `start <id>` · `verify <id>` · `reset <id>` ·
`clean` · `doctor`  (`dashboard` takes `--port`, `--no-open`, `--share`, `--host`, `--key`, `--multi-user`)

The running server caches the catalog in memory. After adding or editing scenarios:

```bash
curl -X POST http://127.0.0.1:4100/api/catalog/reload
```

Restart the server instead if you changed anything under `server/`.

## Using the dashboard

Three panes, always in sync:

| Pane | Contents |
|---|---|
| Left | Catalogue — opens on **Path** (6 stages); **Categories** toggle; level filters; unsolved-only; progress bar |
| Centre | Title, level chips, summary, mental model, danger callout, runnable steps, check results, pitfalls, cheatsheet |
| Right | HEAD, commit-graph SVG, the three areas, working-tree files (click to edit), refs, stash, reflog, terminal |

Three equivalent ways to drive it — all end at the same repo:
1. Press **Run** on a step
2. Type git yourself in the terminal (allow-list: `git`, `ls`, `cat`, `pwd`, `echo`)
3. Click a file and edit it (this is how conflict resolution is taught)

Then **Check my work**. Keys: `/` search, `n` next unsolved, `c` cheatsheet, `Esc` close.

## Current state

- **127 scenarios**, all 20 categories, **0 failures** across the whole suite
- 894 runnable steps · 571 final checks · 644 per-step checks
- 26 beginner · 42 intermediate · 36 advanced · 23 expert
- 145 files, 27 commits

Per category: setup 7 · snapshots 8 · staging 6 · history 11 · branching 7 · merging 6 ·
rebase 6 · remotes 10 · undo 6 · stash 5 · tags 5 · cherry-pick 5 · scale 7 · hooks 5 ·
workflows 5 · rewriting 6 · forensics 5 · internals 6 · incidents 6 · cicd 5

Learning path (`curriculum.json`), 6 stages, all 127 placed:
foundations 26 · everyday 20 · collaboration 18 · recovery 20 · rewriting 19 · mastery 24

## Layout

```
shakhactl.py        the CLI
server/
  app.py            stdlib http.server + JSON API
  gitsandbox.py     the ONLY place git is executed; hard path guard
  catalog.py        loads scenarios/ + curriculum.json
  grader.py         declarative checks against the real repo
web/                index.html + app.js + style.css (vanilla, no build)
scenarios/<ID>/     scenario.json (+ optional explain.md, unused so far)
curriculum.json     the 6-stage ordered learning path
tools/
  test_scenarios.py the regression suite
docs/               AUTHORING.md, CONTEXT.md, DEPLOY.md
.github/workflows/  scenarios.yml (CI)
Dockerfile          the public deployment image (multi-user)
workspaces/         disposable sandboxes — gitignored
sessions/           per-visitor progress, multi-user only — gitignored
progress.json       local progress — gitignored
```

## Safety model

- Every command runs inside `workspaces/`, behind a resolved-path guard that refuses
  to operate outside it
- Each sandbox gets its **own throwaway global git config**, so scenarios can teach
  `git config --global` without touching the real `~/.gitconfig`
- `GIT_CONFIG_SYSTEM` → null device; stdin closed (nothing can block)
- Terminal accepts an allow-list of binaries only
- Commands run without a shell (argv via `shlex`) unless a scenario explicitly wraps
  in `sh -c`

Scenarios needing a server get a **real bare repo as `origin`**, and optionally a second
clone as a **teammate**. Push rejections, `--force-with-lease`, `pre-receive` hooks and
prune all behave exactly as against a real forge.

## Authoring a scenario

One folder: `scenarios/<ID>/scenario.json`. No server code changes needed.
Full schema in `docs/AUTHORING.md`. Shape:

```json
{ "id": "...", "title": "...", "category": "<one of 20 keys in server/catalog.py>",
  "level": "beginner|intermediate|advanced|expert", "order": 1, "duration_min": 12,
  "summary": "...", "concepts": [...], "mental_model": "...", "danger": "optional",
  "setup": [...], "steps": [...], "verify": [...], "pitfalls": [...],
  "cheatsheet": [["cmd", "what it does"]] }
```

Setup/step **actions**: `run`, `write`, `delete`, `commit`, `init_origin`,
`clone_teammate`. Modifiers: `cwd` (`repo`/`origin`/`teammate`, or any dir **relative to
the sandbox root** — note `repo/vendor/lib`, not `vendor/lib`), `as: teammate`, `env`.

**Checks**: `equals`, `contains`, `not_contains`, `matches`, `empty`, `not_empty`,
`lines`, `code`; modifiers `cwd`, `allow_failure`, `include_stderr`, `label`, `hint`.

New scenarios must be added to `curriculum.json` — `shakhactl doctor` fails otherwise.

Test with:
```bash
python tools/test_scenarios.py <id>     # verbose, one scenario
python tools/test_scenarios.py          # the whole catalogue
```
It runs each scenario's own steps and grades the result — a scenario whose steps do not
solve it is a broken scenario.

## Gotchas already paid for (do not rediscover)

- `grep -c` **exits 1 when the count is zero** → the grader reads it as a failed command.
  Use `grep pattern | wc -l`.
- `git shortlog` **reads stdin** with no revision → always pass `HEAD`.
- `git rev-parse <annotated-tag>` gives the **tag object's** sha → use `<tag>^{}`.
- `git clone --depth` is **ignored for local paths** → use `file://$(pwd)`.
- Relative **submodule URLs** resolve against the superproject's remote URL → clone with
  an absolute path.
- `git diff --cached` is **not empty for a mode-only change** → assert on `--numstat`.
- `git blame` output has **no commit subject** → `--line-porcelain` + grep `^summary`.
- `ORIG_HEAD` is **overwritten by any reset**, including mid-rebase → drop a
  `git branch backup` before a rewrite.
- A **no-op rebase reuses identical commits** → force a real difference to show shas change.
- On Windows `chmod` is a no-op and `core.fileMode` defaults false → use
  `git update-index --chmod=+x`.
- `git add -i` **works through a pipe** (`printf "2\n1\n\nq\n" | git add -i`); its menu
  prints `[s]tatus`, so a literal `"status"` check fails.
- `--no-replace-objects` is a **git-level** flag: `git --no-replace-objects rev-list ...`.
- `git show` prints the commit header even when the diff is empty → use `git diff` when
  asserting emptiness.
- Identical file contents break **rename detection** → give setup files distinct content.
- `core.fsmonitor true` starts a daemon that **holds file handles** → stop it, and the
  sandbox teardown retries on locks.
- Two scenarios are **environment-sensitive**, and fail in the Linux container while
  passing on Windows: `incidents-everything-looks-modified` depends on `core.fileMode`
  defaulting false (it is true on Linux, so the mode bits really do differ), and
  `rebase-conflict-recovery` depends on git >= 2.5x dropping a conflict-emptied commit
  — Debian trixie ships 2.47, which skips the commit up front instead. 125/127 pass in
  the container.
- The **catalog is cached in the running server** — reload or restart after edits.

## Done

M0 sandbox engine · M1 dashboard shell · M2 full loop (steps, terminal, editor, grading,
progress) · M3–M6 the 127-scenario catalogue across all 20 categories · M7 navigation
(filters, progress bar, generated cheatsheet) · M8 the six-stage learning path (UI + CLI
+ CI guard) · CI workflow · published to GitHub and verified by cloning fresh and running
scenarios from the clone.

## Optional, not started

1. **`explain.md` long-form** — the engine renders it; no scenario uses one yet.
2. **Spaced-repetition review mode** — resurface scenarios solved long ago. Needs
   `solved_at` timestamps in `progress.json` (deliberately reverted, out of scope at the time).
3. **More scenarios** — the obvious git surface is covered; diminishing returns.
4. **Progress sync across machines** — `progress.json` is gitignored and local.

## Conventions to keep

- British spelling in prose; symptom-first scenario titles
- Every scenario teaches the *why*, names the danger, and ends with a cheatsheet
- Checks grade repository state, never the route taken — solving by hand in the terminal
  must grade identically to pressing the buttons
- Fake credentials in scenarios must be **unmistakably fake** so forge push-protection
  cannot block a push (`AKIAIOSFODNN7EXAMPLE` is AWS's own documented placeholder and is
  kept deliberately, because a scenario's hook regex matches on it)
