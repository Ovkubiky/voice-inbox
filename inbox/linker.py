"""C6 · Linker & Dedup: attaches an item to a known project and detects duplicates of stored items.

Input: Item (+ C4's project hint) and previously stored items. Output: project name | None, duplicate id | None.
Uses local multilingual-e5-small embeddings (cosine similarity) with thresholds tuned by `eval c6`.
A project hint that literally matches a project name wins over embeddings.
"""

from functools import lru_cache

import numpy as np

from inbox import config

PROJECT_THRESHOLD = 0.84  # best embedding threshold in eval c6 (0.595 acc); pipeline uses link_project_llm (0.798)
DUP_THRESHOLD = 0.96  # best dedup F1 (0.80) in eval c6 threshold sweep


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL, device="cpu")


def embed(texts: list[str], kind: str = "query") -> np.ndarray:
    """e5 models expect 'query: ' / 'passage: ' prefixes."""
    return _model().encode([f"{kind}: {t}" for t in texts], normalize_embeddings=True)


@lru_cache(maxsize=1)
def _project_index() -> tuple[list[str], np.ndarray]:
    projects = config.load_projects()
    return [p["name"] for p in projects], embed([f"{p['name']}: {p['description']}" for p in projects], "passage")


def _stem(s: str) -> str:
    return s.lower().replace("’", "'")[:5]


def link_project(title: str, source_text: str, hint: str | None,
                 threshold: float = PROJECT_THRESHOLD) -> tuple[str | None, float]:
    names, vecs = _project_index()
    if hint:
        for name in names:
            if _stem(name.split()[0]) == _stem(hint.split()[0]) or name.lower() in hint.lower():
                return name, 1.0
    q = embed([f"{title}. {source_text}"])[0]
    sims = vecs @ q
    best = int(np.argmax(sims))
    return (names[best] if sims[best] >= threshold else None), float(sims[best])


def link_project_llm(title: str, source_text: str, note_text: str, hint: str | None = None,
                     model: str | None = None) -> str | None:
    """LLM picks one project from the fixed list (or none). Constrained by an enum in the JSON schema."""
    from typing import Literal, Optional

    from pydantic import create_model

    from inbox.llm import chat_json

    projects = config.load_projects()
    names = tuple(p["name"] for p in projects)
    if hint:  # literal match on the hint is free and reliable
        for name in names:
            if _stem(name.split()[0]) == _stem(hint.split()[0]) or name.lower() in hint.lower():
                return name
    Choice = create_model("ProjectChoice", project=(Optional[Literal[names]], None))  # noqa: N806
    listing = "\n".join(f"- {p['name']}: {p['description']}" for p in projects)
    user = f"Projects:\n{listing}\n\nFull note: {note_text}\nItem: {title} ({source_text})"
    try:
        return chat_json("link_project", user, Choice, model=model).project
    except Exception:
        return None


def find_duplicate(title: str, existing: list[tuple[int, str]],
                   threshold: float = DUP_THRESHOLD) -> tuple[int | None, float]:
    """existing = [(item_id, title)]. Returns (id of the most similar item if above threshold, similarity)."""
    if not existing:
        return None, 0.0
    vecs = embed([t for _, t in existing])
    q = embed([title])[0]
    sims = vecs @ q
    best = int(np.argmax(sims))
    return (existing[best][0] if sims[best] >= threshold else None), float(sims[best])
