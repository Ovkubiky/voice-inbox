---
name: make-eval-data
description: Generate or extend the scripted Ukrainian voice-note evaluation set with gold labels, covering the hard-case checklist. Use when building or growing data/scripted/scripts.jsonl.
---

# Make evaluation data

Output file: `data/scripted/scripts.jsonl`, one JSON object per line, validated by `inbox/schemas.py::GoldNote`.

Record format:
```json
{"id": "n001", "ref_time": "2026-11-10T09:00:00+02:00", "text": "<what the owner will read aloud>",
 "tags": ["multi_item", "relative_date"],
 "items": [{"type": "event", "title": "Дзвінок з Андрієм", "date_phrase": "в четвер о третій",
            "start": "2026-11-12T15:00:00+02:00", "people": ["Андрій"], "project": "Курсова",
            "is_incomplete": false}]}
```

Rules:
- Natural spoken Ukrainian as the owner would say it: casual, with fillers ("так", "ну", "ще"), occasional English words.
  10–60 words per note so recording stays short.
- Types: `task`, `event`, `note`, `idea`. `start` is the gold datetime (for events and tasks with deadlines), computed
  from `ref_time`. **Double-check weekday arithmetic** with Python, never by hand.
- `project` must be one of `data/scripted/projects.json` or null.
- `is_incomplete: true` only for events with no resolvable day, or tasks with an unnamed person ("скинути йому").
- Coverage checklist (tag every note; report counts at the end):
  `multi_item` ≥20, `relative_date` ≥25, `absolute_date` ≥8, `code_switch` ≥12, `names` ≥15, `numbers` ≥8,
  `incomplete` ≥8, `idea_or_note` ≥12, `duplicate_of_other` ≥6 (rephrased repeats of an earlier note's item).
- Vary `ref_time` across weekdays so "в четвер" isn't always the same offset.
- Never copy text from `data/private/`. You may imitate the *style* only.

After writing, run `uv run python -m eval.validate_data` and fix until it passes. Then invoke `crisp-dm-log` (phase: Data Preparation).
