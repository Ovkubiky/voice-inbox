"""Record the scripted evaluation notes, one by one, from the terminal.

Shows each script, press Enter to start, Enter to stop. Saves data/scripted/audio/<id>.wav (16 kHz mono).
Already-recorded notes are skipped, so you can stop (Ctrl+C) and continue later.
Type 'r' + Enter after a recording to redo it.

Run: uv run python scripts/record_eval.py
"""

import json
import queue
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "data" / "scripted" / "scripts.jsonl"
AUDIO = ROOT / "data" / "scripted" / "audio"
SR = 16000
SKIPPED = AUDIO / "skipped.txt"  # notes the owner chose not to record (excluded from audio evals)


def record() -> np.ndarray:
    q: queue.Queue = queue.Queue()
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", callback=lambda d, *_: q.put(d.copy())):
        input("   🔴 recording… press Enter to stop")
    chunks = []
    while not q.empty():
        chunks.append(q.get())
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")


def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    notes = [json.loads(line) for line in SCRIPTS.read_text(encoding="utf-8").splitlines() if line]
    skipped = set(SKIPPED.read_text().split()) if SKIPPED.exists() else set()
    todo = [n for n in notes if not (AUDIO / f"{n['id']}.wav").exists() and n["id"] not in skipped]
    print(f"{len(notes) - len(todo) - len(skipped)}/{len(notes)} recorded, {len(skipped)} skipped. "
          f"{len(todo)} to go. Speak naturally, not like reading.\n")
    for i, n in enumerate(todo, 1):
        while True:
            print(f"[{i}/{len(todo)}] {n['id']}\n   «{n['text']}»")
            if input("   Enter = start, s = skip this note: ").strip().lower() == "s":
                with SKIPPED.open("a") as f:
                    f.write(n["id"] + "\n")
                print("   ⏭  skipped\n")
                break
            audio = record()
            dur = len(audio) / SR
            if dur < 0.5:
                print("   too short, again\n")
                continue
            peak = float(np.abs(audio).max())
            if peak < 0.01:
                print(f"   ⚠️  silence (peak {peak:.3f}) — check the microphone / Terminal mic permission. Again.\n")
                continue
            path = AUDIO / f"{n['id']}.wav"
            sf.write(path, audio, SR)
            level = "ok" if peak > 0.05 else "QUIET, speak louder?"
            print(f"   ✅ saved {path.relative_to(ROOT)} · {dur:.1f}s · level {level}")
            ans = input("   Enter = next, p = play back, r = redo: ").strip().lower()
            while ans == "p":
                sd.play(audio, SR)
                sd.wait()
                ans = input("   Enter = next, p = play back, r = redo: ").strip().lower()
            if ans != "r":
                print()
                break
    print("All done ✅")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped. Run again to continue where you left off.")
