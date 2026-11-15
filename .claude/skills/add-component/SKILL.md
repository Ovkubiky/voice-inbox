---
name: add-component
description: Scaffold a new pipeline component (module, schema, eval stub, CRISP-DM entry) for the voice-inbox project. Use when starting work on any of C1–C8 or a new component.
---

# Add a pipeline component

Input: a component id and name (e.g. `c5 dates`) and a one-line purpose.

Steps:
1. Read `PLAN.md` §2 for the component's input → output and chosen model/tool.
2. Add/extend pydantic models in `inbox/schemas.py` for its input and output.
3. Create `inbox/<name>.py` with:
   - a module docstring: `"""C<n> · <Name>: <purpose>. Input: … Output: …"""`
   - one public function (e.g. `resolve(phrase, ref_time) -> datetime | None`), typed.
   - prompts (if LLM) in `inbox/prompts/<name>.md`, loaded with `inbox.llm.load_prompt`.
4. Add `eval_<id>()` to `eval/run_eval.py`, registered in the `COMPONENTS` dict, reading gold from
   `data/scripted/scripts.jsonl`. It must print a metrics table and save `eval/results/<id>.json` + `.md`.
5. If deterministic, add `tests/test_<name>.py` with 5–10 cases.
6. Run `uv run python eval/run_eval.py --component <id>` and report the numbers.
7. Invoke the `crisp-dm-log` skill (phase: Modeling) with the design choice and why.

Don't wire it into `inbox/pipeline.py` until its eval runs.
