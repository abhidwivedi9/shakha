# Authoring a scenario

A scenario is one folder: `scenarios/<ID>/scenario.json`, plus an optional
`explain.md` for longer prose. Nothing in the server needs to change — the
catalog reads the folder at startup, and `POST /api/catalog/reload` re-reads it
without a restart.

## Skeleton

```json
{
  "id": "S07-stash-rescue",
  "title": "Short, symptom-first title",
  "category": "stash",
  "level": "intermediate",
  "order": 1,
  "duration_min": 12,
  "summary": "One or two sentences. What happens and what it teaches.",
  "concepts": ["stash", "WIP commit"],
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
beginner | intermediate | advanced | expert.

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

Every action takes two optional modifiers:

- `"cwd": "repo" | "origin" | "teammate"` — which working copy to act in.
- `"as": "teammate"` — commit with a different author, so history reads honestly.
- `"env": {...}` — extra environment. This is how interactive rebase is driven
  non-interactively, e.g. `{"GIT_SEQUENCE_EDITOR": "sed -i '2s/^pick/fixup/'"}`.

## Steps

```json
{
  "title": "What the learner is about to do",
  "why": "The paragraph that teaches. Backticks and **bold** render.",
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

Every check runs a real command and asserts on its output. Available assertions:

| Key | Passes when |
|---|---|
| `equals` | trimmed stdout equals the value |
| `contains` | stdout contains the string, or every string in a list |
| `not_contains` | stdout contains none of them |
| `matches` | regex matches (multiline) |
| `empty` / `not_empty` | stdout is blank / is not |
| `lines` | stdout has exactly N lines |
| `code` | the command exited with this code |

Modifiers: `cwd` to check the origin or the teammate clone, `allow_failure` for
commands that are expected to fail, `include_stderr` to assert on both streams,
`label` for the human-readable line in the UI, and `hint` for the nudge shown
when it fails.

Write checks against repository state, never against the learner's route to it —
a scenario solved by hand in the terminal must grade identically to one solved
with the buttons.

## Testing it

```
python shakhactl.py start <id>
python shakhactl.py verify <id>
```

`verify` exits 0 when solved, so it drops straight into CI. Running every
scenario's own steps and then grading is the regression test for the whole
catalog.
