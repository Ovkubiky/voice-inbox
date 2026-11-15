"""C2 · Normalizer: cleans a raw ASR transcript with deterministic rules.

Input: raw transcript (str). Output: clean text (str).
Removes filler words, repeated words, odd apostrophes and spacing. No LLM: cheap, predictable, testable.
"""

import re

APOSTROPHES = re.compile(r"[’ʼ`´‘]")
# Filler words that carry no content in Ukrainian dictation. "так" is NOT removed (it is often meaningful).
FILLERS = re.compile(r"(?<![\w'])(е+|е-е|м+|ем+|ну|типу|короче|коротше|ой)(?![\w'])[,]?\s*", re.IGNORECASE)
REPEATS = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?:;])")
MULTISPACE = re.compile(r"\s{2,}")


def normalize(text: str) -> str:
    t = APOSTROPHES.sub("'", text or "")
    t = FILLERS.sub("", t)
    t = REPEATS.sub(r"\1", t)
    t = SPACE_BEFORE_PUNCT.sub(r"\1", t)
    t = re.sub(r"([,.!?:;])(?=[^\s\d])", r"\1 ", t)  # ensure space after punctuation
    t = re.sub(r"^[\s,.;:]+", "", t)
    t = re.sub(r",\s*([.!?])", r"\1", t)
    t = MULTISPACE.sub(" ", t).strip()
    return t[:1].upper() + t[1:] if t else t
