"""Local LLM client (Ollama). The ONLY place that talks to a language model.

- Structured output: the pydantic schema is passed as Ollama's `format`, the reply is validated, 1 retry.
- Every call is traced to logs/llm_trace.jsonl (model, prompt name, latency, tokens) for debugging and the demo.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from inbox import config

PROMPTS_DIR = Path(__file__).parent / "prompts"
TRACE_FILE = config.ROOT / "logs" / "llm_trace.jsonl"
T = TypeVar("T", bound=BaseModel)

UA_WEEKDAY_NAMES = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _trace(record: dict) -> None:
    TRACE_FILE.parent.mkdir(exist_ok=True)
    with TRACE_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def chat_json(prompt_name: str, user: str, schema: type[T], model: str | None = None) -> T:
    model = model or config.LLM_MODEL
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": load_prompt(prompt_name)}, {"role": "user", "content": user}],
        "format": schema.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
        "keep_alive": "30m",
    }
    if model.startswith("qwen3"):
        payload["think"] = False
    last_err: Exception | None = None
    for attempt in range(2):
        t0 = time.perf_counter()
        resp = httpx.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        content = data["message"]["content"]
        latency = time.perf_counter() - t0
        try:
            parsed = schema.model_validate_json(content)
            ok = True
        except ValidationError as e:
            parsed, ok, last_err = None, False, e
        _trace({"ts": datetime.now().isoformat(timespec="seconds"), "model": model, "prompt": prompt_name,
                "attempt": attempt, "ok": ok, "latency_s": round(latency, 2),
                "in_tokens": data.get("prompt_eval_count"), "out_tokens": data.get("eval_count"),
                "input": user[:500], "output": content[:1000]})
        if ok:
            return parsed
    raise RuntimeError(f"LLM returned invalid JSON twice for {prompt_name}: {last_err}")


class _DateAnswer(BaseModel):
    datetime: str | None


def resolve_date_llm(phrase: str, ref: datetime, context: str) -> str | None:
    """Fallback for date phrases the rules can't handle (e.g. "за два дні до того")."""
    user = (f"Reference time: {ref:%Y-%m-%dT%H:%M} ({UA_WEEKDAY_NAMES[ref.weekday()]})\n"
            f"Note: {context}\nDate phrase: {phrase}")
    try:
        ans = chat_json("date_fallback", user, _DateAnswer)
    except Exception:
        return None
    if ans.datetime and re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", ans.datetime):
        return ans.datetime
    return None
