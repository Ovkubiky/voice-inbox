"""C3 · Segmenter + Classifier: splits one voice note into items and labels each one.

Input: clean note text. Output: list[Segment] (verbatim span + type task/event/note/idea).
One LLM call with a JSON schema (prompt: prompts/segment.md).
"""

from inbox.llm import chat_json
from inbox.schemas import Segment, Segmentation


def segment(text: str, model: str | None = None) -> list[Segment]:
    result = chat_json("segment", text, Segmentation, model=model)
    return [s for s in result.items if s.text.strip()]
