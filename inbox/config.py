"""Runtime configuration (env vars with defaults)."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LLM_MODEL = os.getenv("INBOX_LLM_MODEL", "gemma3:12b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
ASR_MODEL = os.getenv("INBOX_ASR_MODEL", "mlx-community/parakeet-tdt-0.6b-v3")
EMBED_MODEL = os.getenv("INBOX_EMBED_MODEL", "intfloat/multilingual-e5-small")
DB_PATH = Path(os.getenv("INBOX_DB_PATH", ROOT / "inbox.db"))
PORT = int(os.getenv("INBOX_PORT", "8777"))
ICS_DIR = ROOT / "exports"

PROJECTS_FILE = ROOT / "data" / "scripted" / "projects.json"


def load_projects() -> list[dict]:
    return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
