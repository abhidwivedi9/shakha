# Shakha (शाखा — *branch*)

**Learn git A to Z from a dashboard that runs real git.**

Every scenario builds an actual repository on disk. The step buttons run actual
`git` commands, the graph is read out of that repository, the file editor writes
actual files, and the checks grade the repo state — not which buttons you pressed.
There is no simulation layer anywhere in this project.

**127 scenarios across all 20 categories. All 127 pass their own checks.**

```
python shakhactl.py dashboard          # http://127.0.0.1:4100
python shakhactl.py dashboard --share  # ... and from your phone, on the same network
python shakhactl.py dashboard --share --key   # ... behind a key carried in the link
```

Requires Python 3.9+ and git. No pip install, no npm install, no build step.

The dashboard is laid out for a phone as well as a desktop: below 900px the three
panes become one screen at a time with a tab bar — Scenarios, Lesson, Repo — so the
graph, the editor and the terminal all stay usable on a small screen. `--share` binds
every interface and prints the address to open on another device; only do that on a
network you trust, because whoever opens it can drive the sandboxes and the terminal.
`--key` closes that hole: the key becomes part of the link, every request without it
gets a 403, and the first load moves the key into a cookie so it leaves the address
bar. Use it for anything wider than a LAN you own — including a tunnel to the wider
internet, where the key is the only thing standing in front of a real shell sandbox.

## Putting it on a public URL

`Dockerfile` builds the whole thing — Python, git, ssh-keygen for the signing scenarios —
and runs it in `--multi-user` mode, where every browser gets its own sandboxes and its own
progress instead of sharing one set. Static hosts (Firebase Hosting, GitHub Pages) cannot
run it: Shakha is a server executing real git, not a bundle of files. See
[docs/DEPLOY.md](docs/DEPLOY.md) for a free container host, the trade-offs, and how to put
a key in front of it.

## What it looks like

The catalogue opens on **Path** — an ordered route through every scenario in six
stages, from a first commit to the object database — with **Categories** a click
away when you want to look something up instead. `n` jumps to the next thing you
have not solved.

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
python shakhactl.py dashboard --share   # let other devices on your network open it
python shakhactl.py dashboard --key     # lock it behind a key carried in the link
python shakhactl.py dashboard --multi-user  # a sandbox set per browser, for shared URLs
python shakhactl.py list           # every scenario, grouped by category
python shakhactl.py path           # the ordered learning path, with your progress
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
curriculum.json     the ordered learning path, in six stages
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
|---:|---|---:|---|
| 1 | Setup & config | 7 | init, clone anatomy, config precedence, gitignore, CRLF, aliases, conditional identity |
| 2 | Snapshots: add, commit, diff | 8 | the three diffs, amend, restore, rm/mv, clean, the `-a` trap, file recovery |
| 3 | The index, in depth | 6 | stage-then-edit, hunk staging, four ways to unstage, `-N`, the index file itself |
| 4 | History & inspection | 11 | log formats, pickaxe, blame, ranges, shortlog, file lifecycle, trailers, notes |
| 5 | Branching | 7 | ff vs no-ff, detached HEAD, rename/recover, `--contains`, hotfix branches, orphan branches |
| 6 | Merging & conflicts | 6 | conflicts, abort and `-X`/`-s`, modify/delete, rerere, squash vs merge, custom drivers |
| 7 | Rebase | 6 | interactive cleanup, `--onto`, conflict recovery, autosquash, splitting, stacks |
| 8 | Remotes | 10 | tracking, prune, push rejection, `--force-with-lease`, forks, refspecs, offline bundles |
| 9 | Undo & recovery | 6 | reflog rescue, revert, reverting a merge, wrong branch, fsck, dangling blobs |
| 10 | Stash | 5 | basics with `-u`, conflicts and `stash branch`, `--keep-index`, recovery, cross-branch |
| 11 | Tags & releases | 5 | lightweight vs annotated, publishing, describe, retagging damage, signing |
| 12 | Cherry-pick & patches | 5 | backporting, conflicts, format-patch/am, cherry-picking a merge, backport audits |
| 13 | Submodules, worktrees, scale | 7 | worktrees, submodules, subtree, sparse-checkout, shallow vs partial, large files |
| 14 | Hooks & automation | 5 | pre-commit, commit-msg, server-side pre-receive, pre-push, the post-* family |
| 15 | Team workflows | 5 | GitHub flow, git flow, trunk-based, long-branch sync, the review loop |
| 16 | Rewriting history | 6 | purging a secret, author identity, force-push fallout, subdirectory extraction, truncation |
| 17 | Forensics & debugging | 5 | bisect, `bisect run`, reflog timelines, repo integrity, gc and maintenance |
| 18 | Git internals | 6 | plumbing commits, the four object types, refs, packfiles, the hash chain |
| 19 | Real-world incidents | 6 | merge ate my code, oversized push, force push over main, lockfiles, unrelated histories |
| 20 | Release & CI/CD git | 5 | changelogs, monorepo path filters, detached HEAD in CI, semver, verifying deploys |

26 beginner, 42 intermediate, 36 advanced, 23 expert. 894 runnable steps and
571 final checks in total.

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
- **M3–M6 — the catalog** ✅ all 20 categories, 127 scenarios, all passing
- **M7 — navigation** ✅ level filters, unsolved-only, progress bar, generated cheatsheet
- **M8 — the path** ✅ a six-stage curriculum covering all 127 scenarios, in the UI and the CLI

Next: `explain.md` long-form notes for the expert scenarios, and a spaced-repetition
mode that resurfaces scenarios you solved a while ago.

## Licence

Apache-2.0.
