# c6_qwen3-14b · model `qwen3:14b`

| metric | value |
|---|---|
| items | 84 |
| best_project_threshold | 0.84 |
| project_accuracy_embedding_best | 0.595 |
| project_accuracy_llm | 0.869 |
| dedup_pairs_checked | 83 |
| current_thresholds | project=0.84, dup=0.96 |

**project_accuracy_by_threshold(no hint)**

| key | value |
|---|---|
| th=0.78 | 0.536 |
| th=0.8 | 0.536 |
| th=0.82 | 0.571 |
| th=0.84 | 0.595 |
| th=0.86 | 0.583 |
| th=0.88 | 0.452 |

**dedup_f1_by_threshold**

| key | value |
|---|---|
| th=0.86 | 0.158 |
| th=0.88 | 0.207 |
| th=0.9 | 0.375 |
| th=0.92 | 0.522 |
| th=0.94 | 0.75 |
| th=0.95 | 0.727 |
| th=0.96 | 0.8 |
| th=0.97 | 0.8 |

## Worst examples

- `{"id": "n019#0", "ok": false, "title": "Скинути презентацію", "pred": "NLP проєкт", "gold": null, "method": "llm"}`
- `{"id": "n029#0", "ok": false, "title": "Подзвонити щодо ключів", "pred": null, "gold": "Дім", "method": "llm"}`
- `{"id": "n031#0", "ok": false, "title": "Здати звіт по практиці", "pred": "Робота", "gold": null, "method": "llm"}`
- `{"id": "n032#0", "ok": false, "title": "Датасет з Common Voice", "pred": "Курсова", "gold": "NLP проєкт", "method": "llm"}`
- `{"id": "n041#0", "ok": false, "title": "Пароль від вайфаю в бабусі", "pred": null, "gold": "Дім", "method": "llm"}`
