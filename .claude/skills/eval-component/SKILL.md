---
name: eval-component
description: Run and analyse the evaluation of one voice-inbox component (or all), save results, and write a failure analysis. Use after changing a component, a prompt, or the model.
---

# Evaluate a component

Input: component id (`c1`…`c8`, `e2e`, or `all`) and optionally a model (`INBOX_LLM_MODEL`).

Steps:
1. Run `uv run python eval/run_eval.py --component <id>` (prefix `INBOX_LLM_MODEL=<model>` if given).
2. Read `eval/results/<id>.md`. Summarise for the owner in ≤5 lines: the headline metric, how it compares to the
   previous run (check git history of the results file), and whether it is good/ok/bad by these bars:
   - classification macro-F1: good ≥0.85, ok ≥0.70
   - slot exact match / date accuracy: good ≥0.80, ok ≥0.60
   - WER (Ukrainian, read speech): good ≤0.10, ok ≤0.20
   - end-to-end fully-correct notes: good ≥0.60, ok ≥0.40
3. Failure analysis: look at the worst 3 examples and group failures into **causes**
   (ASR error upstream, prompt ambiguity, rule gap, gold label error, model limitation).
   If a gold label is wrong, fix it in `data/scripted/scripts.jsonl` and say so explicitly.
4. Propose **one** concrete fix with the expected effect. Don't apply it unless asked.
5. Invoke `crisp-dm-log` (phase: Evaluation) with the metric, causes, and proposed fix.

Never report a metric you didn't just compute.
