# c5_heldout · model `gemma3:12b`

| metric | value |
|---|---|
| phrases | 30 |
| rules_only_accuracy | 0.9 |
| rules+dateparser+llm_accuracy | 0.933 |

**method_outcomes**

| key | value |
|---|---|
| rules:ok | 27 |
| dateparser:wrong | 1 |
| None:wrong | 1 |
| llm:ok | 1 |

## Worst examples

- `{"phrase": "через пів години", "ref": "2026-11-17T10:00", "gold": "2026-11-17T10:30", "rules_only": "2026-11-17", "full": "2026-11-17", "method": "dateparser", "ok": false, "rules_ok": false}`
- `{"phrase": "на вихідних", "ref": "2026-11-17T10:00", "gold": "2026-11-21", "rules_only": null, "full": null, "method": null, "ok": false, "rules_ok": false}`
