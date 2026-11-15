"""C1 · ASR: transcribes a voice note locally with NVIDIA Parakeet TDT v3 (MLX port for Apple Silicon).

Input: path to an audio file (wav/m4a/mp3; ffmpeg handles decoding). Output: raw transcript (str).
"""

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from inbox import config


@lru_cache(maxsize=1)
def _model():
    from parakeet_mlx import from_pretrained

    return from_pretrained(config.ASR_MODEL)


def _to_wav16k(path: Path) -> Path:
    out = Path(tempfile.mkstemp(suffix=".wav")[1])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)],
                   check=True)
    return out


def transcribe(path: str | Path) -> str:
    wav = _to_wav16k(Path(path))
    try:
        return _model().transcribe(str(wav)).text.strip()
    finally:
        wav.unlink(missing_ok=True)
