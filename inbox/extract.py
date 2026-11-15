"""C4 · Slot Extractor: pulls structured fields out of one item.

Input: one Segment + the whole note (for context like "а ввечері" referring to "завтра").
Output: Slots (title, date_phrase, people, project_hint, priority, unresolved_person).
One LLM call per item (prompt: prompts/extract.md).
"""

from inbox.llm import chat_json
from inbox.schemas import Segment, Slots


def extract(seg: Segment, full_text: str, model: str | None = None) -> Slots:
    user = f"Full note: {full_text}\nItem ({seg.type}): {seg.text}"
    return chat_json("extract", user, Slots, model=model)
