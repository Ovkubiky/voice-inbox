"""C9 · Daily Brief: writes a morning "gazette" from the stored inbox items.

Input: open items (+ items done in the last 2 days), today's date, the project list.
Output: Brief (headline, lede, today's agenda, advice per project, plan of the day, items awaiting an answer).
Grounding: the LLM refers to items only by their numeric id, and ids that don't exist are dropped, so it can't invent
tasks. The result is cached per day in SQLite (one edition per day; "reprint" regenerates it).
"""

import json
import re
import sqlite3
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from inbox import config, store
from inbox.llm import chat_json


class AgendaEntry(BaseModel):
    item_id: int
    advice: str = Field(description="one sentence: why today / how to tackle it")


class ProjectDispatch(BaseModel):
    project: str
    advice: str = Field(description="2-3 sentences: where the project stands and the next concrete step")
    item_ids: list[int] = []


class BriefDraft(BaseModel):
    headline: str = Field(description="newspaper-style headline for the day, max 9 words")
    lede: str = Field(description="2-3 sentence opening paragraph about the day")
    today: list[AgendaEntry] = Field(description="items to do today, most important first, max 6")
    projects: list[ProjectDispatch] = Field(description="one dispatch per project that has open items")
    plan: list[str] = Field(description="3-6 ordered steps for the day, each one short sentence")
    sign_off: str = Field(description="one short encouraging closing line")


class Brief(BriefDraft):
    date: str
    created_at: str
    items: dict[int, dict] = {}  # id -> item row, for rendering titles exactly as stored
    awaiting: list[int] = []  # incomplete items (follow-up questions), chosen by rules, not by the LLM
    raw_stats: dict[str, int] = {}  # what the guards removed (for eval c9)


SCHEMA = """CREATE TABLE IF NOT EXISTS briefs (date TEXT PRIMARY KEY, json TEXT, created_at TEXT)"""


def _describe(it: dict, today: date) -> str:
    when = ""
    if it.get("start"):
        d = datetime.fromisoformat(it["start"]) if "T" in it["start"] else datetime.combine(date.fromisoformat(it["start"]), datetime.min.time())
        delta = (d.date() - today).days
        rel = "TODAY" if delta == 0 else "TOMORROW" if delta == 1 else f"OVERDUE by {-delta}d" if delta < 0 else f"in {delta} days"
        when = f" | when: {it['start']} ({rel})"
    people = f" | with: {', '.join(it['people'])}" if it.get("people") else ""
    proj = f" | project: {it['project']}" if it.get("project") else ""
    flag = " | MISSING INFO" if it.get("is_incomplete") else ""
    done = " | DONE" if it.get("status") == "done" else ""
    return f"#{it['id']} [{it['type']}] {it['title']}{when}{people}{proj}{flag}{done} | said: \"{it.get('source_text', '')}\""


def generate(items: list[dict], today: date, model: str | None = None) -> Brief:
    """Pure function (no DB): used by the server and by the eval."""
    projects = config.load_projects()
    valid = {it["id"]: it for it in items}
    listing = "\n".join(_describe(it, today) for it in items) or "(the inbox is empty)"
    proj_list = "\n".join(f"- {p['name']}: {p['description']}" for p in projects)
    user = (f"Today is {today:%A, %d %B %Y}.\n\nProjects:\n{proj_list}\n\nInbox items:\n{listing}")
    draft = chat_json("brief", user, BriefDraft, model=model)

    open_ids = {i for i, it in valid.items() if it.get("status") != "done"}
    raw = {"today_refs": len(draft.today), "invalid_ids": sum(e.item_id not in valid for e in draft.today),
           "done_in_today": sum(e.item_id in valid and e.item_id not in open_ids for e in draft.today),
           "dispatches": len(draft.projects)}
    draft.today = [e for e in draft.today if e.item_id in open_ids][:6]
    # project membership comes from the store, not from the LLM: drop dispatches for projects with no open items
    for d in draft.projects:
        d.item_ids = sorted(i for i in open_ids if valid[i].get("project") == d.project)
    raw["empty_dispatches"] = sum(not d.item_ids for d in draft.projects)
    draft.projects = [d for d in draft.projects if d.item_ids]

    def unref(text: str) -> str:  # "(item #10)" / "#10" -> «title»
        text = re.sub(r"\s*\((?:item\s*)?#(\d+)\)", lambda m: f" («{valid[int(m[1])]['title']}»)" if int(m[1]) in valid else "", text)
        return re.sub(r"(?:item\s*)?#(\d+)", lambda m: f"«{valid[int(m[1])]['title']}»" if int(m[1]) in valid else "", text)

    draft.plan = [unref(x) for x in draft.plan]
    draft.lede, draft.sign_off = unref(draft.lede), unref(draft.sign_off)
    for e in draft.today:
        e.advice = unref(e.advice)
    for d in draft.projects:
        d.advice = unref(d.advice)
    awaiting = [i for i in open_ids if valid[i].get("is_incomplete")]
    return Brief(**draft.model_dump(), date=today.isoformat(), created_at=datetime.now().isoformat(timespec="minutes"),
                 items={i: valid[i] for i in valid}, awaiting=sorted(awaiting), raw_stats=raw)


def brief_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    recent = (today - timedelta(days=2)).isoformat()
    rows = store.list_items(conn, "open")
    rows += [r for r in store.list_items(conn, "done") if (r.get("created_at") or "") >= recent]
    return rows


def get_or_create(conn: sqlite3.Connection, today: date | None = None, force: bool = False) -> Brief:
    today = today or date.today()
    conn.execute(SCHEMA)
    if not force:
        row = conn.execute("SELECT json FROM briefs WHERE date = ?", (today.isoformat(),)).fetchone()
        if row:
            return Brief.model_validate_json(row[0])
    brief = generate(brief_items(conn, today), today)
    conn.execute("INSERT OR REPLACE INTO briefs (date, json, created_at) VALUES (?,?,?)",
                 (brief.date, brief.model_dump_json(), brief.created_at))
    conn.commit()
    return brief


def cached(conn: sqlite3.Connection, today: date | None = None) -> dict | None:
    conn.execute(SCHEMA)
    row = conn.execute("SELECT json FROM briefs WHERE date = ?", ((today or date.today()).isoformat(),)).fetchone()
    return json.loads(row[0]) if row else None
