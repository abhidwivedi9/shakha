# Shakha (शाखा — *branch*)

**Learn git A to Z from a dashboard that runs real git.**

Every scenario builds an actual repository on disk. The step buttons run actual
`git` commands, the graph is read out of that repository, the file editor writes
actual files, and the checks grade the repo state — not which buttons you pressed.
There is no simulation layer anywhere in this project.

**106 scenarios across all 20 categories. All 106 pass their own checks.**

```
python shakhactl.py dashboard          # http://127.0.0.1:4100
```

Requires Python 3.9+ and git. No pip install, no npm install, no build step.

## What it looks like

Three panes that are always in sync:

| Pane | What it holds |
|---|---|
| Left | The scenario catalog, grouped into 20 categories, with progress ticks |
| Centre | The explanation, the mental model, the danger, then runnable steps |
| Right | Live repo state: HEAD, commit graph, the three areas, refs, stash, reflog, a terminal, and a file editor |

Three ways to drive it, all equivalent because they all end at the same repo:

1. Press **Run** on a step.
2. Type your own command in the terminal (`git`, `ls`, `cat`, `pwd`, `echo`).
3. Click a file and edit it — which is what resolving a merge conflict actually is.

Then press **Check my work**. The checks run real commands against the real
repository, so solving a scenario your own way counts exactly the same.

## CLI

```
python shakhactl.py dashboard      # start the dashboard
python shakhactl.py list           # every scenario, grouped
python shakhactl.py start <id>     # build a sandbox on disk
python shakhactl.py verify <id>    # grade it from the terminal (exit 0 = solved)
python shakhactl.py reset <id>     # rebuild it from scratch
python shakhactl.py clean          # delete every sandbox
python shakhactl.py doctor         # check the toolchain and the catalog
```

## Layout

```
shakhactl.py        the CLI
server/
  app.py            stdlib http.server + JSON API
  gitsandbox.py     the only place git is executed; hard path guard
  catalog.py        loads scenarios/ from disk
  grader.py         declarative checks against the real repo
web/                index.html + app.js + style.css, vanilla, no build
scenarios/<ID>/     scenario.json (+ optional explain.md)
tools/
  test_scenarios.py runs every scenario's own steps and grades them
workspaces/         the sandboxes — gitignored, disposable, rebuilt on demand
```

**Safety.** Every command runs inside `workspaces/`, guarded by a resolved-path
check that refuses to operate outside it. Each sandbox gets its own throwaway
global git config, so a scenario can teach `git config --global` without ever
touching your real `~/.gitconfig`. `GIT_CONFIG_SYSTEM` is pointed at the null
device, stdin is closed so nothing can block, and the free terminal accepts only
an allow-list of binaries.

**Real remotes.** Scenarios that need a server get an actual bare repository as
`origin`, and can add a second clone as a teammate. Push rejections, force-push
protection, `pre-receive` hooks and fetch/prune all behave exactly as they do
against a real forge, because there is no difference.

## Coverage

| # | Category | Scenarios | Covers |
|---|---|---:|---|
| 1 | Setup & config | 6 | init, clone anatomy, config precedence, gitignore, CRLF, aliases |
| 2 | Snapshots | 7 | the three diffs, amend, restore, rm/mv, clean, `-a` trap, file recovery |
| 3 | The index | 5 | stage-then-edit, hunk staging, four ways to unstage, `-N`, the index file |
| 4 | History | 7 | log formats, pickaxe, blame, ranges, shortlog, file lifecycle, trailers |
| 5 | Branching | 6 | ff vs no-ff, detached HEAD, rename/delete/recover, `--contains`, hotfix branches |
| 6 | Merging | 5 | first conflict, abort and `-X`/`-s`, modify/delete, rerere, squash vs merge |
| 7 | Rebase | 6 | interactive cleanup, `--onto`, conflict recovery, autosquash, splitting, stacks |
| 8 | Remotes | 7 | tracking, prune, push rejection, `--force-with-lease`, forks, refspecs |
| 9 | Undo & recovery | 6 | reflog rescue, revert, reverting a merge, wrong branch, fsck, dangling blobs |
| 10 | Stash | 4 | basics with `-u`, conflicts and `stash branch`, `--keep-index`, recovery |
| 11 | Tags | 4 | lightweight vs annotated, publishing, describe, the cost of retagging |
| 12 | Cherry-pick | 4 | backporting, conflicts, format-patch/am, cherry-picking a merge |
| 13 | Scale | 5 | worktrees, submodules, sparse-checkout, shallow vs partial, large files |
| 14 | Hooks | 5 | pre-commit, commit-msg, server-side pre-receive, pre-push, the post-* family |
| 15 | Team workflows | 4 | GitHub flow, git flow, trunk-based, long-branch sync |
| 16 | Rewriting | 4 | purging a secret, author identity, force-push fallout, extracting a subdirectory |
| 17 | Forensics | 5 | bisect, `bisect run`, reflog timelines, repo integrity, gc |
| 18 | Internals | 5 | plumbing commits, the four object types, refs, packfiles, the hash chain |
| 19 | Real incidents | 6 | merge ate my code, oversized push, force push over main, lockfiles, unrelated histories |
| 20 | Release & CI | 5 | changelogs, monorepo path filters, detached HEAD in CI, semver, verifying deploys |

24 beginner, 37 intermediate, 29 advanced, 16 expert. 731 runnable steps and
469 final checks in total.

## Testing the catalog

```
python tools/test_scenarios.py                 # every scenario
python tools/test_scenarios.py <id> [<id>...]  # a few, verbosely
```

It builds each sandbox, runs the scenario's own steps exactly as the dashboard
would, and grades the result. A scenario whose steps do not solve it is a broken
scenario, so this is the regression test for the whole product.

## Adding a scenario

Create `scenarios/<ID>/scenario.json`. No server code changes. See
[docs/AUTHORING.md](docs/AUTHORING.md) for the full schema.

## Roadmap

- **M0 — sandbox engine** ✅ real git execution, path guard, repo-state extractor
- **M1 — dashboard shell** ✅ catalog, lesson pane, commit graph, refs, reflog
- **M2 — the full loop** ✅ step buttons, free terminal, file editor, grading, progress
- **M3–M6 — the catalog** ✅ all 20 categories, 106 scenarios, all passing

Next: search and filtering in the catalog pane, per-category progress summaries,
and a printable cheatsheet built from the scenarios you have solved.

## Licence

Apache-2.0.
