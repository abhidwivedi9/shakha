# Shakha (शाखा — *branch*)

**Learn git A to Z from a dashboard that runs real git.**

Every scenario builds an actual repository on disk. The step buttons run actual
`git` commands, the graph is read out of that repository, the file editor writes
actual files, and the checks grade the repo state — not which buttons you pressed.
There is no simulation layer anywhere in this project.

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
workspaces/         the sandboxes — gitignored, disposable, rebuilt on demand
```

Safety: every command runs inside `workspaces/`, guarded by a resolved-path
check that refuses to operate outside it. `GIT_CONFIG_GLOBAL` and
`GIT_CONFIG_SYSTEM` are pointed at the null device, so a scenario can never read
or write your real git config. The free terminal only accepts an allow-list of
binaries.

## Coverage — the A-to-Z plan

| # | Category | Covers |
|---|---|---|
| 1 | Setup & config | init, clone, config levels, aliases, .gitignore, .gitattributes |
| 2 | Snapshots | add, status, commit, amend, diff, restore, rm, mv |
| 3 | The index | staged vs unstaged vs untracked, `add -p` |
| 4 | History | log formats, show, shortlog, grep, pickaxe `-S`, blame |
| 5 | Branching | create/switch, ff vs no-ff, delete, rename, tracking |
| 6 | Merging | text/rename/binary conflicts, ours-theirs, rerere, strategies |
| 7 | Rebase | basic, `-i` squash/fixup/reword/drop/reorder, `--onto`, autosquash |
| 8 | Remotes | fetch vs pull, push, upstream, prune, `--force-with-lease` |
| 9 | Undo & recovery | reset modes, revert, reflog rescue, ORIG_HEAD, dangling commits |
| 10 | Stash | push/pop/apply/drop, `-u`, stash conflicts, stash → branch |
| 11 | Tags | lightweight vs annotated, signing, pushing tags, describe |
| 12 | Cherry-pick | ranges, conflicts, format-patch / am |
| 13 | Scale | submodules, subtree, worktrees, sparse-checkout, partial clone, LFS |
| 14 | Hooks | pre-commit, commit-msg, pre-push, server-side hooks |
| 15 | Team workflows | GitHub flow, git flow, trunk-based, fork+PR, protected branches |
| 16 | Rewriting history | filter-repo, purging a leaked secret, shared-branch rebase disaster |
| 17 | Forensics | `bisect run`, blame `-C`, reflog forensics, fsck, gc |
| 18 | Internals | blob/tree/commit objects, cat-file, hash-object, refs, packfiles |
| 19 | Real incidents | committed to main, lost work, CRLF hell, wrong author, 500MB file |
| 20 | Release & CI | release branches, semantic tags, changelog, monorepo path filters |

## Roadmap

- **M0 — sandbox engine** ✅ real git execution, path guard, repo-state extractor
- **M1 — dashboard shell** ✅ catalog, lesson pane, commit graph, refs, reflog
- **M2 — the full loop** ✅ step buttons, free terminal, file editor, grading, progress
- **M3 — pack 1** categories 1–7 (~30 scenarios)
- **M4 — collaboration** categories 8–12 and 15 (~28 scenarios), on real bare remotes
- **M5 — advanced** categories 13, 14, 16–18 (~30 scenarios)
- **M6 — incidents & polish** categories 19–20, search, streaks, cheatsheet export

Shipped so far: 6 scenarios spanning beginner to advanced, one per proving
mechanism — plain commands, branching, a real conflict needing a file edit,
a `reset --hard` recovered from the reflog, a rejected push against a real bare
origin with a second teammate clone, and a scripted interactive rebase.

## Adding a scenario

Create `scenarios/<ID>/scenario.json`. No server code changes. See
[docs/AUTHORING.md](docs/AUTHORING.md) for the full schema.

## Licence

Apache-2.0.
