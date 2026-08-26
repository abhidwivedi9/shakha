"""Scenario catalog: plain folders on disk, no database.

Adding a scenario means adding a folder with scenario.json (+ optional
explain.md). Nothing in the server needs to change, which is what keeps the
A-to-Z content push cheap.
"""

from __future__ import annotations

import json
from pathlib import Path

# Display order and human labels for the 20 categories that make up A-to-Z git.
CATEGORIES = [
    ("setup", "Setup & config"),
    ("snapshots", "Snapshots: add, commit, diff"),
    ("staging", "The index, in depth"),
    ("history", "History & inspection"),
    ("branching", "Branching"),
    ("merging", "Merging & conflicts"),
    ("rebase", "Rebase"),
    ("remotes", "Remotes"),
    ("undo", "Undo & recovery"),
    ("stash", "Stash"),
    ("tags", "Tags & releases"),
    ("cherrypick", "Cherry-pick & patches"),
    ("scale", "Submodules, worktrees, scale"),
    ("hooks", "Hooks & automation"),
    ("workflows", "Team workflows"),
    ("rewriting", "Rewriting history"),
    ("forensics", "Forensics & debugging"),
    ("internals", "Git internals"),
    ("incidents", "Real-world incidents"),
    ("cicd", "Release & CI/CD git"),
]

CATEGORY_LABELS = dict(CATEGORIES)
CATEGORY_ORDER = {key: index for index, (key, _) in enumerate(CATEGORIES)}

LEVELS = ["beginner", "intermediate", "advanced", "expert"]


class Scenario(dict):
    """A scenario is just its JSON plus the rendered explanation."""

    @property
    def id(self) -> str:
        return self["id"]


class Catalog:
    def __init__(self, scenarios_dir: Path):
        self.dir = Path(scenarios_dir)
        self._cache = {}
        self.reload()

    def reload(self) -> None:
        self._cache = {}
        if not self.dir.exists():
            return
        for folder in sorted(self.dir.iterdir()):
            manifest = folder / "scenario.json"
            if not manifest.is_file():
                continue
            try:
                with open(manifest, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                data = {
                    "id": folder.name,
                    "title": folder.name,
                    "category": "setup",
                    "level": "beginner",
                    "broken": "scenario.json could not be read: %s" % exc,
                }
            data.setdefault("id", folder.name)
            data.setdefault("category", "setup")
            data.setdefault("level", "beginner")
            data.setdefault("steps", [])
            data.setdefault("verify", [])
            data.setdefault("duration_min", 10)
            data["folder"] = str(folder)

            explain = folder / "explain.md"
            data["explain"] = explain.read_text(encoding="utf-8") if explain.is_file() else ""
            self._cache[data["id"]] = Scenario(data)

    # ---- lookups ----------------------------------------------------------

    def get(self, scenario_id: str):
        return self._cache.get(scenario_id)

    def all(self) -> list:
        return sorted(
            self._cache.values(),
            key=lambda s: (CATEGORY_ORDER.get(s.get("category"), 99),
                           s.get("order", 999), s.get("title", "")),
        )

    def summary(self) -> dict:
        """Everything the left-hand catalog pane needs, grouped by category."""
        groups = {}
        for scenario in self.all():
            key = scenario.get("category", "setup")
            groups.setdefault(key, []).append({
                "id": scenario["id"],
                "title": scenario.get("title", scenario["id"]),
                "level": scenario.get("level", "beginner"),
                "summary": scenario.get("summary", ""),
                "duration_min": scenario.get("duration_min", 10),
                "steps": len(scenario.get("steps", [])),
                "danger": scenario.get("danger"),
                "broken": scenario.get("broken"),
            })
        return {
            "categories": [
                {"key": key, "label": label, "scenarios": groups.get(key, [])}
                for key, label in CATEGORIES
            ],
            "total": len(self._cache),
            "levels": LEVELS,
        }
