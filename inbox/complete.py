"""C7 · Completeness check: decides whether an item needs a follow-up question.

Input: Item (+ whether C4 saw an unresolved pronoun). Output: same Item with is_incomplete / question set.
Pure rules, so it is predictable *when* the app asks:
  - an event without a resolved day
  - an item that refers to a person only by a pronoun ("скинути йому")
"""

from inbox.schemas import Item


def check(item: Item, unresolved_person: bool = False) -> Item:
    questions = []
    if item.type == "event" and not item.start:
        questions.append(f"Коли саме «{item.title}»? Назви день і, якщо є, час.")
    if unresolved_person and not item.people:
        questions.append(f"Кого саме стосується «{item.title}»?")
    item.is_incomplete = bool(questions)
    item.question = " ".join(questions) or None
    return item
