"""Summary of the recorded eval audio: how many notes are recorded, and which are missing, too short or too quiet.

Run: uv run python scripts/check_recordings.py
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
ids = [json.loads(l)["id"] for l in (ROOT / "data/scripted/scripts.jsonl").read_text().splitlines() if l]
audio = ROOT / "data/scripted/audio"
skipped_f = audio / "skipped.txt"
skipped = set(skipped_f.read_text().split()) if skipped_f.exists() else set()
done, missing, bad, total = 0, [], [], 0.0
for i in ids:
    f = audio / f"{i}.wav"
    if not f.exists():
        if i not in skipped:
            missing.append(i)
        continue
    x, sr = sf.read(f)
    dur, peak = len(x) / sr, float(np.abs(x).max()) if len(x) else 0.0
    total += dur
    done += 1
    if dur < 1.5 or peak < 0.05:
        bad.append(f"{i} ({dur:.1f}s, peak {peak:.2f})")
print(f"Recorded: {done}/{len(ids)} · skipped {len(skipped)} · total {total/60:.1f} min")
print("Suspicious (short/quiet):", ", ".join(bad) or "none ✅")
print("Missing:", f"{len(missing)} (first: {missing[0]})" if missing else "none ✅")
