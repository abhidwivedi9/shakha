# Authoring a scenario

A scenario is one folder: `scenarios/<ID>/scenario.json`, plus an optional
`explain.md` for longer prose. Nothing in the server needs to change — the
catalog reads the folder at startup, and `POST /api/catalog/reload` re-reads it
without a restart.

## Skeleton

```json
{
  "id": "stash-recover-dropped",
  "title": "Short, symptom-first title",
  "category": "stash",
  "level": "intermediate",
  "order": 4,
  "duration_min": 12,
  "summary": "One or two sentences. What happens and what it teaches.",
  "concepts": ["stash entries are commits", "fsck --unreachable"],
  "mental_model": "The sentence that makes the feature click.",
  "danger": "Optional. Shown in a red callout.",
  "setup": [ ... ],
  "steps": [ ... ],
  "verify": [ ... ],
  "pitfalls": ["..."],
  "cheatsheet": [["git stash", "what it does"]]
}
```

`category` must be one of the 20 keys in `server/catalog.py`. `level` is
beginner | intermediate | advanced | expert. `order` sorts within the category.

## Setup actions

`setup` is a list of declarative actions, replayed from scratch every time the
learner presses Start or Rebuild. Available actions:

| Action | Meaning |
|---|---|
| `{"run": "git init -q -b main"}` | run a command (no shell — argv is split with shlex) |
| `{"write": {"path": "a.py", "content": "..."}}` | write a file |
| `{"delete": "a.py"}` | delete a file or directory |
| `{"commit": {"message": "...", "add": "-A"}}` | add then commit |
| `{"init_origin": true, "push_branch": "main"}` | create a real bare origin and push to it |
| `{"clone_teammate": true}` | clone origin into `teammate/`, a second real working copy |

Every action takes three optional modifiers:

- `"cwd"` — where to run. `repo`, `origin` and `teammate` are built in; any
  other value is a directory **relative to the sandbox root**, which is how
  worktree, extra-clone and submodule scenarios reach their directories. Note
  that a path inside the repo is written `repo/vendor/lib`, not `vendor/lib`.
- `"as": "teammate"` — commit with a different author, so history reads honestly.
- `"env": {...}` — extra environment. This is how interactive rebase is driven
  non-interactively, e.g. `{"GIT_SEQUENCE_EDITOR": "sed -i '2s/^pick/fixup/'"}`,
  and how `FILTER_BRANCH_SQUELCH_WARNING` is set for filter-branch scenarios.

There is no shell, so `cmd1 && cmd2`, pipes, `||` and `$(...)` do not work in a
bare `run`. Wrap them: `{"run": "sh -c 'git merge x || true'"}`.

## Steps

```json
{
  "title": "What the learner is about to do",
  "why": "The paragraph that teaches. Backticks and **bold** render.",
  "cwd": "teammate",
  "actions": [ {"write": {"path": "config.yaml", "content": "..."}} ],
  "commands": ["git add config.yaml", "git commit --no-edit"],
  "expect": "What good output looks like.",
  "verify": [ {"cmd": "git status --porcelain", "not_contains": "UU "} ]
}
```

`actions` run first, then `commands`. Use `run` instead of `commands` for a
single command. A step's own `verify` block decides whether it ticks green; a
step without one ticks as soon as it runs.

Order matters and bites: `fixup` folds into the line above it, so drop unwanted
commits *before* squashing, not after.

## Checks

Every check runs a real command and asserts on its output.

| Key | Passes when |
|---|---|
| `equals` | trimmed stdout equals the value |
| `contains` | stdout contains the string, or every string in a list |
| `not_contains` | stdout contains none of them |
| `matches` | regex matches (multiline) |
| `empty` / `not_empty` | stdout is blank / is not |
| `lines` | stdout has exactly N lines |
| `code` | the command exited with this code |

Modifiers: `cwd` to check the origin or another clone, `allow_failure` for
commands expected to fail, `include_stderr` to assert on both streams, `label`
for the human-readable line in the UI, and `hint` for the nudge shown on failure.

Write checks against repository state, never against the learner's route to it —
a scenario solved by hand in the terminal must grade identically to one solved
with the buttons.

## Lessons from writing 106 of them

These all cost a debugging round the first time:

- **`grep -c` exits 1 when the count is zero**, which the grader reads as a
  failed command. Use `grep pattern | wc -l` in checks.
- **`git shortlog` reads stdin** when given no revision and stdin is not a
  terminal. Always pass `HEAD`.
- **`git rev-parse <annotated-tag>`** gives the tag object's sha, not the
  commit's. Use `<tag>^{}` for the commit.
- **`git clone --depth` is ignored for local paths.** Use `file://$(pwd)` when a
  scenario needs a genuinely shallow clone.
- **Relative submodule URLs** resolve against the superproject's remote URL, so
  clone with an absolute path in submodule scenarios.
- **`git diff --cached` is not empty for a mode-only change** — it prints the
  `old mode`/`new mode` header. Assert on `--numstat` instead.
- **`git blame` output has no commit subject.** Use `--line-porcelain` and grep
  for `^summary`.
- **`ORIG_HEAD` is overwritten** by any reset, including one you run mid-rebase.
  Drop a `git branch backup` before a rewrite and compare against that.
- **A no-op rebase reuses the identical commits**, so it does not demonstrate
  that shas change. Force a real difference (`--exec 'git commit --amend
  --author=...'`).
- **On Windows `chmod` is a no-op** and `core.fileMode` defaults to false. Use
  `git update-index --chmod=+x` to demonstrate mode changes portably.

## Testing it

```
python shakhactl.py start <id>
python shakhactl.py verify <id>
python tools/test_scenarios.py <id>     # runs the steps AND grades, verbosely
python tools/test_scenarios.py          # the whole catalog
```

`verify` exits 0 when solved, so it drops straight into CI. Running every
scenario's own steps and then grading is the regression test for the catalog,
and every scenario in the repository passes it.
