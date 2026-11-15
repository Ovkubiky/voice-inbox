"""Validate data/scripted/scripts.jsonl against the GoldNote schema and report tag coverage.

Run: uv run python -m eval.validate_data
"""

import json
from collections import Counter

from inbox.config import ROOT, load_projects
from inbox.schemas import GoldNote

SCRIPTS = ROOT / "data" / "scripted" / "scripts.jsonl"
TARGETS = {"multi_item": 20, "relative_date": 25, "absolute_date": 8, "code_switch": 12, "names": 15,
           "numbers": 8, "incomplete": 8, "idea_or_note": 12, "duplicate_of_other": 6}


def load_gold() -> list[GoldNote]:
    return [GoldNote.model_validate_json(line) for line in SCRIPTS.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    notes = load_gold()
    projects = {p["name"] for p in load_projects()}
    ids = {n.id for n in notes}
    errors = []
    for n in notes:
        for i, item in enumerate(n.items):
            if item.project and item.project not in projects:
                errors.append(f"{n.id}#{i}: unknown project {item.project!r}")
            if item.duplicate_of and item.duplicate_of.split("#")[0] not in ids:
                errors.append(f"{n.id}#{i}: duplicate_of points to missing note")
            if item.type in ("note", "idea") and item.start:
                errors.append(f"{n.id}#{i}: {item.type} should not have a start")
    tags = Counter(t for n in notes for t in n.tags)
    types = Counter(i.type for n in notes for i in n.items)
    print(f"notes: {len(notes)}  items: {sum(types.values())}  types: {dict(types)}")
    for tag, target in TARGETS.items():
        mark = "OK " if tags[tag] >= target else "LOW"
        print(f"  [{mark}] {tag:<20} {tags[tag]:>3} (target ≥{target})")
    if errors:
        print("ERRORS:", *errors, sep="\n  ")
        raise SystemExit(1)
    print("All records valid.")


if __name__ == "__main__":
    main()
