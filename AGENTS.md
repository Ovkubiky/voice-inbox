# AGENTS.md — rules for the coding agent

Project: **Голосовий інбокс**, a local Ukrainian voice-note inbox (UCU NLP Assignment 1).
Read `PLAN.md` for scope, architecture, and the build order.

The owner is a **vibecoder**: they steer, you write the code. That means:
- Explain what you changed in 2–4 plain sentences, not code walkthroughs.
- Every step must end with **one command the owner can run** that prints a clear result (a metric, "OK", a URL).
- Don't ask the owner to debug Python. If something fails, fix it or propose a scope cut.

## Process: CRISP-DM (mandatory)
Work in CRISP-DM phases and **log every meaningful decision** in `report/crisp_dm_log.md` under the right phase:
1. **Business Understanding**: who the user is, what counts as useful output, success criteria.
2. **Data Understanding**: what data exists (TypeWhisper history, public datasets checked), its quirks.
3. **Data Preparation**: eval scripts, gold labels, normalization.
4. **Modeling**: component choices, prompts, models tried and why.
5. **Evaluation**: metrics per component, failure analysis, comparison of models.
6. **Deployment**: server, menu-bar app, how to run.

Use the `crisp-dm-log` skill for log entries. If you try something and abandon it, log that too, since negative results go in the report.

## Architecture rules
- Pipeline components C1–C8 each live in **one module** in `inbox/` (see `PLAN.md` §2), with typed input/output from `inbox/schemas.py` (pydantic v2).
- **No component without an eval.** Each component has a function in `eval/run_eval.py` reachable via `--component <id>`;
  results go to `eval/results/<id>.json` (raw) and `eval/results/<id>.md` (table + worst 3 examples).
- LLM calls only go through `inbox/llm.py` (Ollama, structured JSON output, pydantic validation, 1 retry). Never call Ollama directly elsewhere.
- Prompts live in `inbox/prompts/*.md`, never as long strings in Python.
- Deterministic first: if rules can do it reliably (dates, completeness), use rules and use the LLM only as a fallback.
- Config via env vars with defaults in `inbox/config.py` (`INBOX_LLM_MODEL`, `INBOX_DB_PATH`, `INBOX_PORT`).

## Code conventions
- Python 3.12, managed by `uv`. Add dependencies with `uv add`, never with `pip install`.
- Keep code boring and small: plain functions, no class hierarchies, no frameworks beyond FastAPI, Gradio, and pydantic.
- Type hints on public functions. One short docstring per module explaining its component role.
- Tests for deterministic code (`dates.py`, `normalize.py`, `complete.py`) in `tests/`, run with `uv run pytest -q`.
- Swift code lives only in `macapp/`; it talks to the backend over HTTP at `http://127.0.0.1:8777`, never by importing Python.

## Privacy rules (hard)
- `data/private/` holds the owner's real notes: **never commit it, never print its contents in full, never quote it in the report.**
  Aggregate numbers and paraphrased examples only.
- Never send any data to external APIs. All models run locally.
- Never commit `.env`, `*.db`, `.venv/`, `macapp/build/`.

## Definition of done (per step)
1. The code runs: the step's check command passes.
2. The eval for the touched component runs, and its number is reported to the owner.
3. A CRISP-DM log entry is written.
4. Changes are committed with a clear message (only when the owner asks, or at the end of a planned step).

## When stuck
If the same approach fails twice, stop. Explain the blocker in one paragraph, propose the next item on the cut list
(`PLAN.md` §5), and log it.
