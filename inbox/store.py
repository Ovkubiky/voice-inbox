"""C8 · Store & Export: persists notes/items in SQLite and exports dated items as .ics calendar files.

Input: NoteResult. Output: the same with DB ids filled in; .ics bytes on request.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from icalendar import Calendar, Event

from inbox import config
from inbox.schemas import Item, NoteResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, recorded_at TEXT, raw_transcript TEXT, clean_text TEXT,
                                  audio_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, note_id INTEGER REFERENCES notes(id), type TEXT, title TEXT,
                                  source_text TEXT, date_phrase TEXT, start TEXT, people TEXT, project TEXT,
                                  priority TEXT, is_incomplete INTEGER, question TEXT, duplicate_of INTEGER,
                                  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_note(conn: sqlite3.Connection, note: NoteResult, audio_path: str | None = None) -> NoteResult:
    cur = conn.execute("INSERT INTO notes (recorded_at, raw_transcript, clean_text, audio_path) VALUES (?,?,?,?)",
                       (note.recorded_at, note.raw_transcript, note.clean_text, audio_path))
    note.note_id = cur.lastrowid
    for item in note.items:
        cur = conn.execute(
            "INSERT INTO items (note_id, type, title, source_text, date_phrase, start, people, project, priority,"
            " is_incomplete, question, duplicate_of) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (note.note_id, item.type, item.title, item.source_text, item.date_phrase, item.start,
             json.dumps(item.people, ensure_ascii=False), item.project, item.priority, int(item.is_incomplete),
             item.question, item.duplicate_of))
        item.id = cur.lastrowid
    conn.commit()
    return note


def recent_notes(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    """Latest notes with their items' titles/types/status, newest first (for the board's history strip)."""
    notes = [dict(r) for r in conn.execute(
        "SELECT id, recorded_at, clean_text, audio_path IS NOT NULL AS voice, created_at FROM notes ORDER BY id DESC LIMIT ?",
        (limit,))]
    for n in notes:
        n["items"] = [dict(r) for r in conn.execute(
            "SELECT id, type, title, status, is_incomplete FROM items WHERE note_id = ? ORDER BY id", (n["id"],))]
    return notes


def row_to_item(row: sqlite3.Row) -> Item:
    d = dict(row)
    return Item(id=d["id"], type=d["type"], title=d["title"], source_text=d["source_text"] or "",
                date_phrase=d["date_phrase"], start=d["start"], people=json.loads(d["people"] or "[]"),
                project=d["project"], priority=d["priority"] or "normal", is_incomplete=bool(d["is_incomplete"]),
                question=d["question"], duplicate_of=d["duplicate_of"])


def list_items(conn: sqlite3.Connection, status: str = "open") -> list[dict]:
    """status: 'open' | 'done' | 'dismissed' | 'all' (= open + done)."""
    if status == "all":
        rows = conn.execute("SELECT * FROM items WHERE status IN ('open','done') ORDER BY COALESCE(start, '9999'), id DESC")
    else:
        rows = conn.execute("SELECT * FROM items WHERE status = ? ORDER BY COALESCE(start, '9999'), id DESC", (status,))
    return [dict(r) | {"people": json.loads(r["people"] or "[]")} for r in rows]


def existing_titles(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return [(r["id"], r["title"]) for r in conn.execute("SELECT id, title FROM items WHERE status = 'open'")]


def get_item(conn: sqlite3.Connection, item_id: int) -> Item | None:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_item(row) if row else None


def update_item(conn: sqlite3.Connection, item: Item) -> None:
    conn.execute("UPDATE items SET type=?, title=?, date_phrase=?, start=?, people=?, project=?, is_incomplete=?,"
                 " question=? WHERE id=?",
                 (item.type, item.title, item.date_phrase, item.start, json.dumps(item.people, ensure_ascii=False),
                  item.project, int(item.is_incomplete), item.question, item.id))
    conn.commit()


PATCHABLE = {"type", "project", "status", "title"}


def patch_item(conn: sqlite3.Connection, item_id: int, fields: dict) -> dict | None:
    """Board edits (drag between columns): updates only whitelisted fields. Returns the updated row."""
    fields = {k: v for k, v in fields.items() if k in PATCHABLE}
    if fields:
        conn.execute(f"UPDATE items SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                     (*fields.values(), item_id))
        conn.commit()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return dict(row) | {"people": json.loads(row["people"] or "[]")} if row else None


def set_status(conn: sqlite3.Connection, item_id: int, status: str) -> None:
    conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()


def to_ics(item: Item) -> bytes:
    """Event: 1 hour (or all-day). Task with deadline: all-day event 'Дедлайн: ...'."""
    if not item.start:
        raise ValueError("item has no start date")
    cal = Calendar()
    cal.add("prodid", "-//Voice Inbox//UA//")
    cal.add("version", "2.0")
    ev = Event()
    ev.add("uid", f"voice-inbox-{item.id or 0}@local")
    ev.add("summary", item.title if item.type == "event" else f"Дедлайн: {item.title}")
    ev.add("dtstamp", datetime.now())
    if "T" in item.start:
        start = datetime.fromisoformat(item.start)
        ev.add("dtstart", start)
        ev.add("dtend", start + timedelta(hours=1))
    else:
        day = date.fromisoformat(item.start)
        ev.add("dtstart", day)
        ev.add("dtend", day + timedelta(days=1))
    desc = item.source_text + (f"\nЛюди: {', '.join(item.people)}" if item.people else "")
    ev.add("description", desc)
    if item.project:
        ev.add("categories", [item.project])
    cal.add_component(ev)
    return cal.to_ical()
