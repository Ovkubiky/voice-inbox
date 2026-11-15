"""Export TypeWhisper dictation history to JSONL.

TypeWhisper (macOS) keeps history in a Core Data SQLite file. We copy it
(plus WAL/SHM files) to a temp dir first so the live app database is never
touched, then read the fields useful for building an evaluation set.

Usage:
    python scripts/export_typewhisper.py [--out data/private/typewhisper_history.jsonl] [--ukrainian-only]
"""

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TW_DIR = Path.home() / "Library/Application Support/TypeWhisper"
APPLE_EPOCH_OFFSET = 978307200  # Core Data timestamps count from 2001-01-01
CYRILLIC = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ")

QUERY = """
SELECT ZTIMESTAMP, ZDURATIONSECONDS, ZWORDSCOUNT, ZAPPNAME, ZMODELUSED,
       ZLANGUAGE, ZRAWTEXT, ZFINALTEXT, ZAUDIOFILENAME
FROM ZTRANSCRIPTIONRECORD
ORDER BY ZTIMESTAMP
"""


def has_cyrillic(text: str | None) -> bool:
    return bool(text) and any(ch in CYRILLIC for ch in text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/private/typewhisper_history.jsonl")
    parser.add_argument("--ukrainian-only", action="store_true",
                        help="keep only records containing Cyrillic text")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        for f in TW_DIR.glob("history.store*"):
            shutil.copy2(f, tmp)
        conn = sqlite3.connect(Path(tmp) / "history.store")
        rows = conn.execute(QUERY).fetchall()
        conn.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with out.open("w", encoding="utf-8") as fh:
        for ts, dur, words, app, model, lang, raw, final, audio in rows:
            if args.ukrainian_only and not has_cyrillic(final or raw):
                continue
            audio_path = TW_DIR / "audio" / audio if audio else None
            record = {
                "timestamp": datetime.fromtimestamp(ts + APPLE_EPOCH_OFFSET, tz=timezone.utc).isoformat()
                if ts is not None else None,
                "duration_sec": dur,
                "words": words,
                "app": app,
                "model": model,
                "language": lang or None,
                "has_cyrillic": has_cyrillic(final or raw),
                "raw_text": raw,
                "final_text": final,
                "audio_path": str(audio_path) if audio_path and audio_path.exists() else None,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1

    print(f"Exported {kept} of {len(rows)} records -> {out}")


if __name__ == "__main__":
    main()
