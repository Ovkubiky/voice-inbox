"""Local backend: FastAPI serving the board web app (/), the JSON API (menu-bar app + board), and eval results (/ui).

Run: uv run inbox-server   ->  http://127.0.0.1:8777/
"""

import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from inbox import config, pipeline, store

if "INBOX_PROJECTS_FILE" not in os.environ and config.APP_PROJECTS_FILE.exists():
    config.PROJECTS_FILE = config.APP_PROJECTS_FILE  # live project list, not the eval fixture

app = FastAPI(title="Voice Inbox")
WEB_DIR = Path(__file__).parent / "web"
conn = store.connect()
AUDIO_DIR = config.ROOT / "data" / "private" / "recordings"


def _keep_audio(upload: UploadFile) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "note.wav").suffix or ".wav"
    dest = AUDIO_DIR / f"{datetime.now():%Y%m%d-%H%M%S}{suffix}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(upload.file, fh)
    return dest


@app.get("/")
def root():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/gazette")
def gazette_page():
    return FileResponse(WEB_DIR / "gazette.html")


@app.get("/architecture")
def architecture_page():
    return FileResponse(WEB_DIR / "architecture.html")


@app.get("/brief")
def get_brief(cached_only: bool = False):
    """Today's gazette (C9). Generated once per day and cached; cached_only=true never calls the LLM."""
    from inbox import brief

    if cached_only:
        return brief.cached(conn) or {}
    return brief.get_or_create(conn).model_dump()


@app.post("/brief/reprint")
def reprint_brief():
    from inbox import brief

    return brief.get_or_create(conn, force=True).model_dump()


@app.get("/projects")
def projects():
    return config.load_projects()


@app.get("/evals")
def evals():
    """Headline metrics of every saved eval run, for the board's Eval panel."""
    import json

    out = []
    for f in sorted((config.ROOT / "eval" / "results").glob("*.json")):
        if f.name.startswith("cache_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        flat = {k: v for k, v in d.get("metrics", {}).items() if not isinstance(v, dict | list)}
        out.append({"component": d.get("component", f.stem), "model": d.get("model"), "metrics": flat})
    return out


class Patch(BaseModel):
    type: str | None = None
    project: str | None = None
    status: str | None = None
    title: str | None = None
    clear_project: bool = False


@app.get("/health")
def health():
    return {"ok": True, "llm": config.LLM_MODEL, "asr": config.ASR_MODEL}


# Notes being processed right now (in memory), so the board can show "transcribing… / splitting…" live,
# including notes sent from the menu-bar app. Failed jobs are kept for a while so the error is visible.
JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run_job(kind: str, preview: str, fn):
    job_id = uuid.uuid4().hex[:8]
    job = {"job": job_id, "kind": kind, "preview": preview, "stage": "queued", "status": "processing",
           "started_at": datetime.now().isoformat(timespec="seconds")}
    with _jobs_lock:
        JOBS[job_id] = job
    try:
        note = fn(lambda st: job.update(stage=st))
        with _jobs_lock:
            JOBS.pop(job_id, None)
        return note.model_dump()
    except Exception as e:
        job.update(status="failed", stage="failed", error=str(e)[:200])
        raise


@app.post("/notes")
def post_note_audio(file: UploadFile = File(...)):
    path = _keep_audio(file)
    return _run_job("voice", "", lambda st: pipeline.process_audio(str(path), conn=conn, on_stage=st))


@app.post("/notes/text")
def post_note_text(text: str = Form(...)):
    return _run_job("text", text[:120], lambda st: pipeline.process_text(text, conn=conn, on_stage=st))


@app.get("/notes/recent")
def recent_notes(limit: int = 8):
    """History strip: notes in progress (live stage), failed ones, then the latest stored notes."""
    with _jobs_lock:
        jobs = sorted(JOBS.values(), key=lambda j: j["started_at"], reverse=True)
    return {"active": jobs, "notes": store.recent_notes(conn, limit)}


@app.delete("/notes/jobs/{job_id}")
def dismiss_job(job_id: str):
    with _jobs_lock:
        JOBS.pop(job_id, None)
    return {"ok": True}


@app.get("/items")
def get_items(status: str = "open"):
    return store.list_items(conn, status)


@app.post("/items/{item_id}/answer")
def answer(item_id: int, answer: str = Form(...)):
    try:
        return pipeline.answer_question(conn, item_id, answer).model_dump()
    except KeyError:
        raise HTTPException(404, "item not found")


@app.patch("/items/{item_id}")
def patch(item_id: int, body: Patch):
    fields = body.model_dump(exclude_none=True, exclude={"clear_project"})
    if body.clear_project:
        fields["project"] = None
    row = store.patch_item(conn, item_id, fields)
    if row is None:
        raise HTTPException(404, "item not found")
    return row


@app.post("/items/{item_id}/done")
def done(item_id: int):
    store.set_status(conn, item_id, "done")
    return {"ok": True}


@app.get("/items/{item_id}.ics")
def ics(item_id: int):
    item = store.get_item(conn, item_id)
    if not item or not item.start:
        raise HTTPException(404, "no dated item")
    return Response(store.to_ics(item), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="item-{item_id}.ics"'})


def _mount_ui() -> None:
    import gradio as gr

    from inbox.ui import build_ui

    gr.mount_gradio_app(app, build_ui(conn), path="/ui")


def main() -> None:
    _mount_ui()
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    print(f"Voice inbox running: http://127.0.0.1:{config.PORT}/  (LLM: {config.LLM_MODEL})")
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
