"""Wires C1–C8 together: one voice note (audio or text) -> stored inbox items."""

import sqlite3
import time
from collections.abc import Callable
from datetime import datetime

from inbox import complete, dates, extract, linker, normalize, segment, store
from inbox.schemas import Item, NoteResult


def process_text(text: str, recorded_at: datetime | None = None, conn: sqlite3.Connection | None = None,
                 raw: str | None = None, model: str | None = None, audio_path: str | None = None,
                 on_stage: Callable[[str], None] | None = None) -> NoteResult:
    recorded_at = recorded_at or datetime.now()
    stage = on_stage or (lambda _s: None)
    stage("cleaning")
    timings: dict[str, float] = {}

    t = time.perf_counter()
    clean = normalize.normalize(text)  # C2
    timings["c2_normalize"] = time.perf_counter() - t

    stage("splitting")
    t = time.perf_counter()
    segs = segment.segment(clean, model=model)  # C3
    timings["c3_segment"] = time.perf_counter() - t

    existing = store.existing_titles(conn) if conn else []
    items: list[Item] = []
    timings.update(c4_extract=0.0, c5_dates=0.0, c6_link=0.0)
    for n, seg in enumerate(segs, 1):
        stage(f"reading item {n} of {len(segs)}")
        t = time.perf_counter()
        slots = extract.extract(seg, clean, model=model)  # C4
        timings["c4_extract"] += time.perf_counter() - t

        t = time.perf_counter()
        res = dates.resolve(slots.date_phrase, recorded_at, context=clean) if seg.type in ("task", "event") \
            else dates.Resolution(None, None)  # C5
        timings["c5_dates"] += time.perf_counter() - t

        t = time.perf_counter()
        project = linker.link_project_llm(slots.title, seg.text, clean, slots.project_hint, model=model)  # C6
        dup, _ = linker.find_duplicate(slots.title, existing)
        timings["c6_link"] += time.perf_counter() - t

        item = Item(type=seg.type, title=slots.title, source_text=seg.text, date_phrase=slots.date_phrase,
                    start=res.value, people=slots.people, project=project, priority=slots.priority,
                    duplicate_of=dup)
        items.append(complete.check(item, slots.unresolved_person))  # C7

    note = NoteResult(recorded_at=recorded_at.isoformat(timespec="minutes"), raw_transcript=raw or text,
                      clean_text=clean, items=items, timings={k: round(v, 2) for k, v in timings.items()})
    if conn:
        stage("saving")
        t = time.perf_counter()
        store.save_note(conn, note, audio_path)  # C8
        note.timings["c8_store"] = round(time.perf_counter() - t, 3)
    return note


def process_audio(path: str, recorded_at: datetime | None = None, conn: sqlite3.Connection | None = None,
                  model: str | None = None, on_stage: Callable[[str], None] | None = None) -> NoteResult:
    from inbox import asr

    if on_stage:
        on_stage("transcribing")
    t = time.perf_counter()
    raw = asr.transcribe(path)  # C1
    asr_time = time.perf_counter() - t
    note = process_text(raw, recorded_at, conn, raw=raw, model=model, audio_path=str(path), on_stage=on_stage)
    note.timings = {"c1_asr": round(asr_time, 2), **note.timings}
    return note


def answer_question(conn: sqlite3.Connection, item_id: int, answer: str) -> Item:
    """Follow-up loop (C7 -> C4/C5): the user's answer fills the missing date or person."""
    item = store.get_item(conn, item_id)
    if item is None:
        raise KeyError(item_id)
    now = datetime.now()
    if not item.start:
        res = dates.resolve(answer, now, context=f"{item.source_text}. {answer}")
        if res.value:
            item.start, item.date_phrase = res.value, answer
    if not item.people and not any(ch.isdigit() for ch in answer):
        names = [w.strip(".,") for w in answer.split() if w[:1].isupper()]
        if names:
            item.people = names
    complete.check(item, unresolved_person=not item.people and "Кого" in (item.question or ""))
    store.update_item(conn, item)
    return item
