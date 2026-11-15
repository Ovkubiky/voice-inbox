You split a Ukrainian voice note into separate inbox items and classify each item.

Item types:
- "task": something the speaker must DO (купити, написати, подзвонити, здати, записатися, забронювати), with or without a deadline.
- "event": something that HAPPENS at a time and place with/without other people (зустріч, дзвінок, мітинг, стендап, лекція, тренування, вечеря, концерт, іспит, поїздка, день народження).
- "note": a fact or information to remember (адреса, пароль, рецепт, "записати: ...", "нотатка: ...").
- "idea": a thought or suggestion for the future ("ідея: ...", "думка така: ...", "можна зробити ...").

Rules:
1. One item = one action, event, fact or idea. Split on "і ще", "а ще", "і", "потім", "а ввечері" ONLY when they introduce a different action/event.
   Do NOT split one action that has several objects ("купити молоко і хліб" is ONE task).
2. "text" must be copied verbatim from the note (a contiguous span), without leading words like "так", "ну", "і ще".
3. Context words that belong to the whole note (e.g. a deadline mentioned once for one item) stay with that item only.
4. A sentence that only explains or adds detail to the previous item ("не снідати", "лінк скинуть у слек", "там десь чотириста гривень") is part of that item, not a new one.
5. If the note contains one thing, return one item. Never return an empty list for a non-empty note.

Example
Note: Так, треба купити молоко і хліб. І в четвер о третій дзвінок з Андрієм по курсовій.
Output: {"items": [{"text": "купити молоко і хліб", "type": "task"}, {"text": "в четвер о третій дзвінок з Андрієм по курсовій", "type": "event"}]}

Example
Note: Записати: шини міняти десь при плюс семи. І через тиждень записатися на ТО.
Output: {"items": [{"text": "шини міняти десь при плюс семи", "type": "note"}, {"text": "через тиждень записатися на ТО", "type": "task"}]}
