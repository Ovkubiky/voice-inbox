"""C5 · Date Resolver: turns a Ukrainian date/time phrase into a concrete local datetime.

Input: date phrase (e.g. "в четвер о третій") + reference time (when the note was recorded).
Output: Resolution(value="YYYY-MM-DDTHH:MM" | "YYYY-MM-DD" | None, method="rules" | "dateparser" | "llm" | None).

Strategy: hand-written Ukrainian rules first (deterministic, covers the labelling conventions in
data/scripted/build_scripts.py), then `dateparser` (languages=["uk"]), then an optional LLM fallback that
sees the whole note (for things like "за два дні до того").
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MONTHS = {"січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6, "липня": 7,
          "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12}

# Weekday stems; negative lookbehind stops "понеділок" matching "неділ", lookahead stops "четвертій" -> "четвер".
WEEKDAYS = [(r"понеділ", 0), (r"вівтор", 1), (r"серед|середу", 2), (r"четвер(?!т)", 3),
            (r"п'ятниц", 4), (r"субот", 5), (r"(?<!по)неділ", 6)]

# Ordinal stems shared by hours ("о третій", "на третю") and days ("третього").
ORD_STEMS = {"перш": 1, "друг": 2, "трет": 3, "четверт": 4, "п'ят": 5, "шост": 6, "сьом": 7, "восьм": 8,
             "дев'ят": 9, "десят": 10, "одинадцят": 11, "дванадцят": 12, "тринадцят": 13, "чотирнадцят": 14,
             "п'ятнадцят": 15, "шістнадцят": 16, "сімнадцят": 17, "вісімнадцят": 18, "дев'ятнадцят": 19,
             "двадцят": 20, "тридцят": 30}
_STEM_ALT = "|".join(sorted(ORD_STEMS, key=len, reverse=True))

CARDINALS = {"один": 1, "одну": 1, "одна": 1, "два": 2, "дві": 2, "три": 3, "чотири": 4, "п'ять": 5, "шість": 6,
             "сім": 7, "вісім": 8, "дев'ять": 9, "десять": 10}
MINUTE_WORDS = {"п'ятнадцять": 15, "двадцять": 20, "тридцять": 30, "сорок": 40, "сорок п'ять": 45, "п'ятдесят": 50}

RE_DAY_ORD = re.compile(rf"(?:(двадцять|тридцять)\s+)?(?<![\w'])({_STEM_ALT})ь?ого\b")  # третього, п'ятого
RE_DAY_NUM = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")")
RE_HOUR_WORD = re.compile(rf"(?:\bо|\bна|\bдо)\s+({_STEM_ALT})(?:ій|у|ю|ої)\b(?:\s+(сорок п'ять|п'ятнадцять|двадцять|тридцять|сорок|п'ятдесят)\b)?")
RE_HALF = re.compile(rf"пів\s+на\s+({_STEM_ALT})(?:у|ю|ій)\b")  # пів на третю, пів на п'яту
RE_CLOCK = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:год\w*)?\b")
RE_IN_N = re.compile(r"через\s+(\d+|" + "|".join(CARDINALS) + r")?\s*(дн|день|тиж|годин|хвилин)\w*")


@dataclass
class Resolution:
    value: str | None
    method: str | None


def _clean(phrase: str) -> str:
    return re.sub(r"[’ʼ`]", "'", phrase.lower()).strip()


def _num(token: str | None, default: int = 1) -> int:
    if not token:
        return default
    return int(token) if token.isdigit() else CARDINALS.get(token, default)


def _next_weekday(ref: date, wd: int, next_week: bool) -> date:
    if next_week:
        monday_next = ref + timedelta(days=7 - ref.weekday())
        return monday_next + timedelta(days=wd)
    delta = (wd - ref.weekday()) % 7
    return ref + timedelta(days=delta or 7)


def _find_day(p: str, ref: datetime) -> date | None:
    d = ref.date()
    if "післязавтра" in p:
        return d + timedelta(days=2)
    if "завтра" in p:
        return d + timedelta(days=1)
    if "сьогодні" in p:
        return d
    if m := RE_IN_N.search(p):
        n, unit = _num(m.group(1)), m.group(2)
        if unit.startswith("тиж"):
            return d + timedelta(weeks=n)
        if unit in ("дн", "день"):
            return d + timedelta(days=n)
    if "кінця тижня" in p:
        return d + timedelta(days=max(4 - d.weekday(), 0)) if d.weekday() <= 4 else d + timedelta(days=6 - d.weekday())
    if "кінця місяця" in p:
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])
    for pattern, wd in WEEKDAYS:
        if re.search(rf"(?<![а-яіїєґ']){pattern}", p):
            return _next_weekday(d, wd, next_week="наступн" in p)
    if re.search(r"наступн\w*\s+тижн", p):
        return _next_weekday(d, 0, next_week=True)
    month = next((MONTHS[w] for w in MONTHS if w in p), None)
    if month:
        day_num = None
        if m := RE_DAY_NUM.search(p):
            day_num = int(m.group(1))
        elif m := RE_DAY_ORD.search(p):
            tens = {"двадцять": 20, "тридцять": 30}.get(m.group(1) or "", 0)
            day_num = tens + ORD_STEMS[m.group(2)]
        if day_num:
            try:
                cand = date(d.year, month, day_num)
            except ValueError:
                return None
            return cand if cand >= d else date(d.year + 1, month, day_num)
    return None


def _find_time(p: str) -> tuple[int, int] | None:
    morning = any(w in p for w in ("ранку", "зранку", "вранці", "з ранку"))
    evening = any(w in p for w in ("вечора", "ввечері", "увечері"))
    hour = minute = None
    if m := RE_HALF.search(p):
        hour, minute = ORD_STEMS[m.group(1)] - 1, 30
    elif m := RE_HOUR_WORD.search(p):
        hour, minute = ORD_STEMS[m.group(1)], MINUTE_WORDS.get(m.group(2) or "", 0)
    elif m := re.search(r"\b(?:о|об|на)\s+(\d{1,2})(?:[:.](\d{2}))?\b", p) or re.search(r"\b(\d{1,2})[:.](\d{2})\b", p):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if hour is not None:
        if hour <= 12:
            if evening and hour < 12:
                hour += 12
            elif not morning and 1 <= hour <= 7:
                hour += 12
        return hour % 24, minute
    if "після обіду" in p:
        return 14, 0
    if "обід" in p:
        return 13, 0
    if morning:
        return 9, 0
    if evening:
        return 19, 0
    return None


def resolve_rules(phrase: str, ref: datetime) -> str | None:
    p = _clean(phrase)
    if m := re.search(r"через\s+(\d+|" + "|".join(CARDINALS) + r")?\s*(годин|хвилин)\w*", p):
        n = _num(m.group(1))
        delta = timedelta(hours=n) if m.group(2) == "годин" else timedelta(minutes=n)
        return (ref + delta).strftime("%Y-%m-%dT%H:%M")
    day = _find_day(p, ref)
    tm = _find_time(p)
    if day is None and tm is None:
        return None
    if day is None:  # only a time: today if still ahead, else tomorrow
        day = ref.date() if (tm[0], tm[1]) > (ref.hour, ref.minute) else ref.date() + timedelta(days=1)
    if tm is None:
        return day.isoformat()
    return f"{day.isoformat()}T{tm[0]:02d}:{tm[1]:02d}"


def resolve_dateparser(phrase: str, ref: datetime) -> str | None:
    import dateparser

    dt = dateparser.parse(phrase, languages=["uk"],
                          settings={"RELATIVE_BASE": ref, "PREFER_DATES_FROM": "future"})
    if dt is None:
        return None
    has_time = bool(re.search(r"\d[:.]\d|о\s+\d", phrase))
    return dt.strftime("%Y-%m-%dT%H:%M") if has_time else dt.date().isoformat()


def resolve(phrase: str | None, ref: datetime, context: str | None = None, use_llm: bool = True) -> Resolution:
    if not phrase or not phrase.strip():
        return Resolution(None, None)
    if value := resolve_rules(phrase, ref):
        return Resolution(value, "rules")
    try:
        if value := resolve_dateparser(phrase, ref):
            return Resolution(value, "dateparser")
    except Exception:  # dateparser can raise on odd input; treat as "not resolved"
        pass
    if use_llm:
        from inbox.llm import resolve_date_llm

        if value := resolve_date_llm(phrase, ref, context or phrase):
            return Resolution(value, "llm")
    return Resolution(None, None)
