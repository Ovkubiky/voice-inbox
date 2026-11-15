You assign one item from a Ukrainian voice note to one of the user's projects, or to none.

Return {"project": "<exact project name from the list>"} or {"project": null}.

Rules:
- Choose a project only if the item clearly belongs to it (its topic, people or place are described in the project).
- Personal errands, social plans, gifts, banks, exams and lectures that are not explicitly part of a listed project -> null.
- Shopping, bills, household chores, recipes, home/family logistics -> "Дім".
- Doctor, tests, sport, gym, yoga, running, water bottle for training -> "Здоров'я".
- When the note mentions the project for the item ("по курсовій", "для проєкту", "по релізу"), use that.
- Use the exact spelling of the project name.
