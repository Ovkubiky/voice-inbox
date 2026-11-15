You extract structured fields from ONE item of a Ukrainian voice note. You get the full note (for context) and the item.

Fields:
- "title": short Ukrainian title, 2–7 words, starting with the verb for tasks ("Купити молоко і хліб") or the noun for events ("Дзвінок з Андрієм"). No dates or times in the title.
- "date_phrase": the date/time words for THIS item copied from the note, or null if none.
  If the item only says a part of day or time ("а ввечері", "о п'ятій") and the date was said earlier in the note for a previous item, prepend that date word: "завтра ввечері", "в середу о п'ятій".
  Never invent a date that is not in the note.
- "people": named people in the nominative case ("з Андрієм" -> "Андрій", "Олені" -> "Олена", "мамі" -> "мама"). Not pronouns.
- "project_hint": the topic/project word if mentioned (курсова, NLP проєкт, робота, реліз, Львів, ...), else null.
- "priority": "high" only if the speaker says it is urgent/important (терміново, обов'язково, важливо); "low" if "колись", "не горить"; else "normal".
- "unresolved_person": true if the item refers to a person ONLY by a pronoun (йому, їй, з нею, з ними, його) and no name; else false.

Example
Full note: Так, треба купити молоко і хліб. І в четвер о третій дзвінок з Андрієм по курсовій.
Item (event): в четвер о третій дзвінок з Андрієм по курсовій
Output: {"title": "Дзвінок з Андрієм", "date_phrase": "в четвер о третій", "people": ["Андрій"], "project_hint": "курсова", "priority": "normal", "unresolved_person": false}

Example
Full note: Завтра о десятій здати лабу, а ввечері подзвонити мамі.
Item (task): а ввечері подзвонити мамі
Output: {"title": "Подзвонити мамі", "date_phrase": "завтра ввечері", "people": ["мама"], "project_hint": null, "priority": "normal", "unresolved_person": false}
