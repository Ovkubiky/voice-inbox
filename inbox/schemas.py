"""Typed data passed between pipeline components (C1–C8) and the gold eval format.

Datetimes are local (Europe/Kyiv), naive, serialised as:
  - "YYYY-MM-DDTHH:MM" when a time is known
  - "YYYY-MM-DD"       when only the day is known (all-day / deadline)
"""

from typing import Literal

from pydantic import BaseModel, Field

ItemType = Literal["task", "event", "note", "idea"]
Priority = Literal["low", "normal", "high"]


# ---- C3: segmenter + classifier -------------------------------------------------
class Segment(BaseModel):
    text: str = Field(description="Exact span of the note that describes ONE item")
    type: ItemType


class Segmentation(BaseModel):
    items: list[Segment]


# ---- C4: slot extractor -----------------------------------------------------------
class Slots(BaseModel):
    title: str = Field(description="Short imperative/noun title in Ukrainian, 2-7 words")
    date_phrase: str | None = Field(
        default=None, description="Verbatim date/time words for THIS item, incl. context like 'завтра ввечері'"
    )
    people: list[str] = Field(default_factory=list, description="Named people, nominative case")
    project_hint: str | None = Field(default=None, description="Project/topic word if mentioned")
    priority: Priority = "normal"
    unresolved_person: bool = Field(
        default=False, description="True if the item refers to a person only by pronoun (йому, їй, з ними)"
    )


# ---- Full item after C5–C7 --------------------------------------------------------
class Item(BaseModel):
    type: ItemType
    title: str
    source_text: str
    date_phrase: str | None = None
    start: str | None = None  # see module docstring
    people: list[str] = Field(default_factory=list)
    project: str | None = None
    priority: Priority = "normal"
    is_incomplete: bool = False
    question: str | None = None
    duplicate_of: int | None = None  # DB id of an existing item
    id: int | None = None  # DB id once stored


class NoteResult(BaseModel):
    note_id: int | None = None
    recorded_at: str
    raw_transcript: str
    clean_text: str
    items: list[Item]
    timings: dict[str, float] = Field(default_factory=dict)


# ---- Gold evaluation format -----------------------------------------------------
class GoldItem(BaseModel):
    type: ItemType
    title: str
    date_phrase: str | None = None
    start: str | None = None
    people: list[str] = Field(default_factory=list)
    project: str | None = None
    is_incomplete: bool = False
    duplicate_of: str | None = None  # "<note_id>#<item_index>"


class GoldNote(BaseModel):
    id: str
    ref_time: str  # "YYYY-MM-DDTHH:MM"
    text: str
    tags: list[str] = Field(default_factory=list)
    items: list[GoldItem]
