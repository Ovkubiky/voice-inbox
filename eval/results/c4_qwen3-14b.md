# c4_qwen3-14b · model `qwen3:14b`

| metric | value |
|---|---|
| items_evaluated | 81 |
| title_token_f1 | 0.891 |
| title_match_rate(f1>=0.5) | 0.938 |
| date_phrase_token_f1 | 0.951 |
| date_presence_accuracy | 0.951 |
| people_f1 | 0.833 |
| unresolved_person_accuracy | 0.975 |

## Worst examples

- `{"id": "n004#0", "ok": false, "pred": {"title": "Вечеря з Олею і Марком", "date_phrase": "в п'ятницю о сьомій", "people": ["Олена", "Марк"]}, "gold": {"title": "Вечеря з Олею і Марком", "date_phrase": "в п'ятницю о сьомій", "people": ["Оля", "Марко"]}}`
- `{"id": "n008#0", "ok": false, "pred": {"title": "Зробити віджет", "date_phrase": null, "people": []}, "gold": {"title": "Віджет пропонує час для задачі", "date_phrase": null, "people": []}}`
- `{"id": "n010#1", "ok": false, "pred": {"title": "Показати чернетку науковому керівнику", "date_phrase": "п'ятнадцятого грудня", "people": ["науковий керівник"]}, "gold": {"title": "Показати чернетку науковому керівнику", "date_phrase": null, "people": []}}`
- `{"id": "n011#0", "ok": false, "pred": {"title": "Мітинг з командою", "date_phrase": "в наступну середу о десятій", "people": ["команда"]}, "gold": {"title": "Мітинг з командою по релізу", "date_phrase": "в наступну середу о десятій", "people": []}}`
- `{"id": "n019#0", "ok": false, "pred": {"title": "Скинути презентацію", "date_phrase": "до обіду", "people": ["йому"]}, "gold": {"title": "Скинути презентацію", "date_phrase": "до обіду", "people": []}}`
