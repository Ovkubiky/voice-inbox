"""Component evaluations for the voice inbox. One function per component, each saves JSON + Markdown.

Usage:
  uv run python eval/run_eval.py --component c5
  INBOX_LLM_MODEL=qwen3:14b uv run python eval/run_eval.py --component c3
  uv run python eval/run_eval.py --all

Inputs are isolated where possible so errors are attributed to the right component:
  c3 runs on the gold script text; c4 runs on C3 segments that align to a gold item;
  c5 runs on GOLD date phrases (pure resolver quality) and separately on C4-predicted phrases.
"""

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.metrics import align, confusion, macro_f1, prf, set_f1, token_f1  # noqa: E402
from eval.validate_data import load_gold  # noqa: E402
from inbox import config  # noqa: E402

RESULTS = config.ROOT / "eval" / "results"
TYPES = ["task", "event", "note", "idea"]


def model_tag() -> str:
    return config.LLM_MODEL.replace(":", "-").replace("/", "-")


def save(component: str, metrics: dict, examples: list[dict], md_extra: str = "") -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    if config.LLM_MODEL != "gemma3:12b" and component not in ("c1", "c5", "c5_heldout", "c8"):
        component = f"{component}_{model_tag()}"  # keep the default model's results; comparison runs get a suffix
    payload = {"component": component, "model": config.LLM_MODEL, "run_at": datetime.now().isoformat(timespec="seconds"),
               "metrics": metrics, "examples": examples}
    (RESULTS / f"{component}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# {component} · model `{config.LLM_MODEL}`", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in metrics.items() if not isinstance(v, dict)]
    for k, v in metrics.items():
        if isinstance(v, dict):
            lines += ["", f"**{k}**", "", "| key | value |", "|---|---|"] + [f"| {a} | {b} |" for a, b in v.items()]
    if md_extra:
        lines += ["", md_extra]
    worst = [e for e in examples if not e.get("ok", True)][:5]
    if worst:
        lines += ["", "## Worst examples", ""] + [f"- `{json.dumps(e, ensure_ascii=False)}`" for e in worst]
    (RESULTS / f"{component}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\n-> saved eval/results/{component}.json / .md")


# ---------------------------------------------------------------- C3 segment + classify
def _c3_cache_path() -> Path:
    return RESULTS / f"cache_c3_{model_tag()}.json"


def run_c3_predictions(force: bool = False) -> dict:
    from inbox.segment import segment

    path = _c3_cache_path()
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    preds = {}
    for n in load_gold():
        t0 = time.perf_counter()
        try:
            segs = [s.model_dump() for s in segment(n.text)]
        except Exception as e:  # count as a failure, keep going
            segs, _ = [], print(f"  {n.id}: C3 failed: {e}")
        preds[n.id] = {"segments": segs, "latency": round(time.perf_counter() - t0, 2)}
        print(f"  c3 {n.id}: {len(segs)} items ({preds[n.id]['latency']}s)")
    RESULTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preds, ensure_ascii=False, indent=1), encoding="utf-8")
    return preds


def eval_c3(force: bool = False) -> None:
    preds = run_c3_predictions(force)
    count_ok = tp = fp = fn = 0
    type_pairs, examples, latencies = [], [], []
    for n in load_gold():
        segs = preds[n.id]["segments"]
        latencies.append(preds[n.id]["latency"])
        gold_texts = [g.title + " " + (g.date_phrase or "") + " " + " ".join(g.people) for g in n.items]
        pairs = align([s["text"] for s in segs], gold_texts)
        count_ok += len(segs) == len(n.items)
        tp += len(pairs)
        fp += len(segs) - len(pairs)
        fn += len(n.items) - len(pairs)
        for i, j in pairs:
            type_pairs.append((segs[i]["type"], n.items[j].type))
        ok = len(segs) == len(n.items) and len(pairs) == len(n.items) and all(
            segs[i]["type"] == n.items[j].type for i, j in pairs)
        examples.append({"id": n.id, "ok": ok, "text": n.text, "pred": [(s["type"], s["text"]) for s in segs],
                         "gold": [(g.type, g.title) for g in n.items]})
    mf1, per = macro_f1(type_pairs, TYPES)
    metrics = {"notes": len(examples), "item_count_accuracy": round(count_ok / len(examples), 3),
               **{f"segmentation_{k}": v for k, v in prf(tp, fp, fn).items()},
               "type_accuracy_on_aligned": round(sum(p == g for p, g in type_pairs) / max(len(type_pairs), 1), 3),
               "type_macro_f1": mf1, "type_f1_per_label": per,
               "avg_latency_s": round(sum(latencies) / len(latencies), 2)}
    save("c3", metrics, sorted(examples, key=lambda e: e["ok"]),
         "## Type confusion (aligned items)\n\n" + confusion(type_pairs, TYPES))


# ---------------------------------------------------------------- C4 slot extraction
def eval_c4(force: bool = False) -> None:
    from inbox.extract import extract
    from inbox.schemas import Segment

    preds = run_c3_predictions()
    cache = RESULTS / f"cache_c4_{model_tag()}.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() and not force else {}
    rows, examples = [], []
    for n in load_gold():
        segs = preds[n.id]["segments"]
        gold_texts = [g.title + " " + (g.date_phrase or "") + " " + " ".join(g.people) for g in n.items]
        for i, j in align([s["text"] for s in segs], gold_texts):
            key = f"{n.id}#{j}"
            if key not in cached:
                try:
                    cached[key] = extract(Segment(**segs[i]), n.text).model_dump()
                except Exception as e:
                    cached[key] = {"error": str(e)}
                print(f"  c4 {key}: {cached[key].get('title')}")
            s, g = cached[key], n.items[j]
            if "error" in s:
                rows.append({"title": 0, "date_phrase": 0, "has_date": 0, "people": 0, "unresolved": 0})
                continue
            row = {"title": token_f1(s["title"], g.title),
                   "date_phrase": token_f1(s["date_phrase"], g.date_phrase),
                   "has_date": float(bool(s["date_phrase"]) == bool(g.date_phrase)),
                   "people": set_f1(s["people"], g.people),
                   "unresolved": float(s["unresolved_person"] == (g.is_incomplete and g.type != "event"))}
            rows.append(row)
            ok = row["title"] >= 0.5 and row["date_phrase"] >= 0.6 and row["people"] == 1.0
            examples.append({"id": key, "ok": ok, "pred": {k: s[k] for k in ("title", "date_phrase", "people")},
                             "gold": {"title": g.title, "date_phrase": g.date_phrase, "people": g.people}})
    cache.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    avg = lambda k: round(sum(r[k] for r in rows) / max(len(rows), 1), 3)  # noqa: E731
    metrics = {"items_evaluated": len(rows), "title_token_f1": avg("title"),
               "title_match_rate(f1>=0.5)": round(sum(r["title"] >= 0.5 for r in rows) / max(len(rows), 1), 3),
               "date_phrase_token_f1": avg("date_phrase"), "date_presence_accuracy": avg("has_date"),
               "people_f1": avg("people"), "unresolved_person_accuracy": avg("unresolved")}
    save("c4", metrics, sorted(examples, key=lambda e: e["ok"]))


# ---------------------------------------------------------------- C5 date resolution
def phrase_kind(p: str) -> str:
    p = p.lower()
    if any(m in p for m in ("листопада", "грудня")):
        return "absolute"
    if "через" in p or "кінця" in p or "до того" in p:
        return "offset/period"
    if "наступн" in p:
        return "next-week"
    if any(w in p for w in ("сьогодні", "завтра", "післязавтра")):
        return "today/tomorrow"
    if any(w in p for w in ("понеділ", "вівтор", "серед", "четвер", "п'ятниц", "субот", "неділ")):
        return "weekday"
    return "time-only/other"


def eval_c5(use_llm: bool = True) -> None:
    from inbox.dates import resolve

    by_kind, by_method, examples = defaultdict(list), Counter(), []
    for n in load_gold():
        ref = datetime.fromisoformat(n.ref_time)
        for j, g in enumerate(n.items):
            if not g.date_phrase:
                continue
            r = resolve(g.date_phrase, ref, context=n.text, use_llm=use_llm)
            ok = r.value == g.start
            day_ok = (r.value or "")[:10] == (g.start or "")[:10]
            kind = phrase_kind(g.date_phrase)
            by_kind[kind].append(ok)
            by_method[f"{r.method}:{'ok' if ok else 'wrong'}"] += 1
            examples.append({"id": f"{n.id}#{j}", "ok": ok, "day_ok": day_ok, "phrase": g.date_phrase,
                             "ref": n.ref_time, "pred": r.value, "gold": g.start, "method": r.method})
    total = len(examples)
    metrics = {"phrases": total, "exact_accuracy": round(sum(e["ok"] for e in examples) / total, 3),
               "day_accuracy": round(sum(e["day_ok"] for e in examples) / total, 3),
               "accuracy_by_phrase_kind": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_kind.items())},
               "method_outcomes": dict(by_method)}
    save("c5", metrics, sorted(examples, key=lambda e: e["ok"]))


def eval_c5_heldout() -> None:
    """Phrases written AFTER the rules, never used to develop them, measuring how well the rules generalise."""
    from inbox.dates import resolve

    path = config.ROOT / "data" / "scripted" / "dates_heldout.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    examples = []
    for r in rows:
        ref = datetime.fromisoformat(r["ref_time"])
        rules_only = resolve(r["phrase"], ref, use_llm=False)
        full = resolve(r["phrase"], ref, use_llm=True)
        examples.append({"phrase": r["phrase"], "ref": r["ref_time"], "gold": r["start"], "rules_only": rules_only.value,
                         "full": full.value, "method": full.method, "ok": full.value == r["start"],
                         "rules_ok": rules_only.value == r["start"]})
    n = len(examples)
    metrics = {"phrases": n, "rules_only_accuracy": round(sum(e["rules_ok"] for e in examples) / n, 3),
               "rules+dateparser+llm_accuracy": round(sum(e["ok"] for e in examples) / n, 3),
               "method_outcomes": dict(Counter(f"{e['method']}:{'ok' if e['ok'] else 'wrong'}" for e in examples))}
    save("c5_heldout", metrics, sorted(examples, key=lambda e: e["ok"]))


# ---------------------------------------------------------------- C1 ASR + C2 normalizer
def _words(t: str) -> str:
    import re

    return " ".join(re.findall(r"[\w']+", t.lower().replace("’", "'")))


def run_asr_predictions(force: bool = False) -> dict:
    from inbox.asr import transcribe

    audio_dir = config.ROOT / "data" / "scripted" / "audio"
    cache = RESULTS / "cache_c1_asr.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() and not force else {}
    for n in load_gold():
        wav = audio_dir / f"{n.id}.wav"
        if wav.exists() and n.id not in cached:
            t0 = time.perf_counter()
            cached[n.id] = {"text": transcribe(wav), "latency": round(time.perf_counter() - t0, 2)}
            print(f"  asr {n.id}: {cached[n.id]['text'][:70]}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    return cached


def eval_c1(force: bool = False) -> None:
    import jiwer

    from eval.metrics import stems
    from inbox.normalize import normalize

    asr = run_asr_predictions(force)
    if not asr:
        print("No recordings yet: run `uv run python scripts/record_eval.py` first.")
        return
    gold = {n.id: n for n in load_gold()}
    refs, hyps, hyps_norm, examples, ent_hit, ent_total = [], [], [], [], 0, 0
    for nid, pred in asr.items():
        ref, hyp = _words(gold[nid].text), _words(pred["text"])
        refs.append(ref), hyps.append(hyp), hyps_norm.append(_words(normalize(pred["text"])))
        # entity recall: names + date words must survive ASR, they drive everything downstream
        ents = set()
        for g in gold[nid].items:
            ents |= {p.lower()[:4] for p in g.people} | stems(g.date_phrase)
        hyp_stems = {w[:4] for w in hyp.split()} | {w[:5] for w in hyp.split()}
        ent_hit += sum(1 for e in ents if e in hyp_stems)
        ent_total += len(ents)
        w = jiwer.wer(ref, hyp)
        examples.append({"id": nid, "ok": w <= 0.1, "wer": round(w, 3), "gold": gold[nid].text, "asr": pred["text"]})
    lat = [p["latency"] for p in asr.values()]
    metrics = {"notes": len(refs), "WER": round(jiwer.wer(refs, hyps), 3), "CER": round(jiwer.cer(refs, hyps), 3),
               "entity_recall(names+date words)": round(ent_hit / max(ent_total, 1), 3),
               "C2_WER_after_normalizer": round(jiwer.wer(refs, hyps_norm), 3),
               "avg_latency_s": round(sum(lat) / len(lat), 2)}
    save("c1", metrics, sorted(examples, key=lambda e: -e["wer"]))


# ---------------------------------------------------------------- C6 linker & dedup
def eval_c6() -> None:
    from inbox import linker

    notes = load_gold()
    # Project linking, isolated: gold title + full note text, no hint (pure embedding quality), threshold sweep
    names_vecs = linker._project_index()
    proj_rows = []
    for n in notes:
        for j, g in enumerate(n.items):
            _, sim = linker.link_project(g.title, n.text, None, threshold=0.0)
            best, _ = linker.link_project(g.title, n.text, None, threshold=-1)
            proj_rows.append((best, sim, g.project, f"{n.id}#{j}", g.title))
    sweep = {}
    for th in [0.78, 0.80, 0.82, 0.84, 0.86, 0.88]:
        acc = sum((b if s >= th else None) == gp for b, s, gp, *_ in proj_rows) / len(proj_rows)
        sweep[f"th={th}"] = round(acc, 3)
    best_th = max(sweep, key=sweep.get)
    th = float(best_th.split("=")[1])
    # Dedup: process items in note order, compare with all earlier gold titles
    seen: list[tuple[str, str]] = []
    dup_rows = []
    for n in notes:
        for j, g in enumerate(n.items):
            key = f"{n.id}#{j}"
            if seen:
                _, sim = linker.find_duplicate(g.title, [(i, t) for i, (_, t) in enumerate(seen)], threshold=2)
                dup_rows.append((sim, g.duplicate_of is not None, key, g.title))
            seen.append((key, g.title))
    # LLM variant: same isolated input (gold title + note), the LLM picks from the project list
    llm_rows = []
    for n in notes:
        for j, g in enumerate(n.items):
            pred = linker.link_project_llm(g.title, g.title, n.text)
            llm_rows.append({"id": f"{n.id}#{j}", "ok": pred == g.project, "title": g.title, "pred": pred,
                             "gold": g.project, "method": "llm"})
    llm_acc = round(sum(r["ok"] for r in llm_rows) / len(llm_rows), 3)
    dsweep = {}
    for dth in [0.86, 0.88, 0.90, 0.92, 0.94, 0.95, 0.96, 0.97]:
        tp = sum(1 for s, gd, *_ in dup_rows if s >= dth and gd)
        fp = sum(1 for s, gd, *_ in dup_rows if s >= dth and not gd)
        fn = sum(1 for s, gd, *_ in dup_rows if s < dth and gd)
        dsweep[f"th={dth}"] = prf(tp, fp, fn)["f1"]
    examples = [{"id": k, "ok": (b if s >= th else None) == gp, "title": t, "pred": b if s >= th else None,
                 "sim": round(s, 3), "gold": gp} for b, s, gp, k, t in proj_rows]
    metrics = {"items": len(proj_rows), "project_accuracy_by_threshold(no hint)": sweep,
               "best_project_threshold": th, "project_accuracy_embedding_best": sweep[best_th],
               "project_accuracy_llm": llm_acc,
               "dedup_pairs_checked": len(dup_rows), "dedup_f1_by_threshold": dsweep,
               "current_thresholds": f"project={linker.PROJECT_THRESHOLD}, dup={linker.DUP_THRESHOLD}"}
    _ = names_vecs
    save("c6", metrics, sorted(llm_rows, key=lambda e: e["ok"]) + sorted(examples, key=lambda e: e["ok"]))


# ---------------------------------------------------------------- C7 completeness (on pipeline inputs)
def eval_c7() -> None:
    """Uses C3 types + C4 slots (cached) + C5 dates, so it measures the follow-up decision the user would see."""
    from inbox.complete import check
    from inbox.dates import resolve
    from inbox.schemas import Item

    preds = run_c3_predictions()
    cache = RESULTS / f"cache_c4_{model_tag()}.json"
    if not cache.exists():
        print("Run c4 first (needs its cache).")
        return
    slots = json.loads(cache.read_text(encoding="utf-8"))
    tp = fp = fn = tn = 0
    examples = []
    for n in load_gold():
        segs = preds[n.id]["segments"]
        gold_texts = [g.title + " " + (g.date_phrase or "") + " " + " ".join(g.people) for g in n.items]
        for i, j in align([s["text"] for s in segs], gold_texts):
            s = slots.get(f"{n.id}#{j}")
            if not s or "error" in s:
                continue
            start = resolve(s["date_phrase"], datetime.fromisoformat(n.ref_time), n.text, use_llm=False).value
            item = check(Item(type=segs[i]["type"], title=s["title"], source_text=segs[i]["text"], start=start,
                              people=s["people"]), s["unresolved_person"])
            gold = n.items[j].is_incomplete
            tp += item.is_incomplete and gold
            fp += item.is_incomplete and not gold
            fn += (not item.is_incomplete) and gold
            tn += (not item.is_incomplete) and not gold
            examples.append({"id": f"{n.id}#{j}", "ok": item.is_incomplete == gold, "asked": item.question,
                             "gold_incomplete": gold, "text": segs[i]["text"]})
    metrics = {"items": tp + fp + fn + tn, **{f"ask_{k}": v for k, v in prf(tp, fp, fn).items()},
               "accuracy": round((tp + tn) / max(tp + fp + fn + tn, 1), 3), "tp": tp, "fp": fp, "fn": fn}
    save("c7", metrics, sorted(examples, key=lambda e: e["ok"]))


# ---------------------------------------------------------------- C8 store & export
def eval_c8() -> None:
    import tempfile

    from icalendar import Calendar

    from inbox import store
    from inbox.schemas import Item, NoteResult

    with tempfile.TemporaryDirectory() as tmp:
        conn = store.connect(Path(tmp) / "t.db")
        stored = roundtrip_ok = ics_total = ics_ok = 0
        examples = []
        for n in load_gold():
            items = [Item(type=g.type, title=g.title, source_text=n.text, date_phrase=g.date_phrase, start=g.start,
                          people=g.people, project=g.project) for g in n.items]
            note = store.save_note(conn, NoteResult(recorded_at=n.ref_time, raw_transcript=n.text,
                                                    clean_text=n.text, items=items))
            for it in note.items:
                stored += 1
                back = store.get_item(conn, it.id)
                same = back.model_dump(exclude={"id"}) == it.model_dump(exclude={"id"})
                roundtrip_ok += same
                ok_ics = True
                if it.start:
                    ics_total += 1
                    try:
                        ev = Calendar.from_ical(store.to_ics(back)).walk("VEVENT")[0]
                        dt = ev.decoded("dtstart")
                        ok_ics = dt.isoformat()[:len(it.start)] == it.start
                    except Exception:
                        ok_ics = False
                    ics_ok += ok_ics
                examples.append({"id": it.id, "ok": same and ok_ics, "title": it.title, "start": it.start})
    metrics = {"items_stored": stored, "roundtrip_exact_rate": round(roundtrip_ok / stored, 3),
               "ics_files": ics_total, "ics_valid_and_correct_rate": round(ics_ok / max(ics_total, 1), 3)}
    save("c8", metrics, sorted(examples, key=lambda e: e["ok"]))


# ---------------------------------------------------------------- End-to-end
def eval_e2e(source: str = "audio") -> None:
    """Full pipeline per note (C1 if audio exists, else gold text) with a fresh DB so dedup sees earlier notes."""
    import tempfile

    from inbox import pipeline, store

    asr = run_asr_predictions() if source == "audio" else {}
    with tempfile.TemporaryDirectory() as tmp:
        conn = store.connect(Path(tmp) / "e2e.db")
        notes_ok, item_ok, item_total, examples = 0, 0, 0, []
        field_hits = Counter()
        for n in load_gold():
            text = asr[n.id]["text"] if n.id in asr else n.text
            res = pipeline.process_text(text, datetime.fromisoformat(n.ref_time), conn=conn)
            pairs = align([it.title + " " + it.source_text for it in res.items],
                          [g.title + " " + (g.date_phrase or "") for g in n.items])
            matched = {j: res.items[i] for i, j in pairs}
            all_ok = len(res.items) == len(n.items)
            for j, g in enumerate(n.items):
                p = matched.get(j)
                checks = {"found": p is not None,
                          "type": bool(p) and p.type == g.type,
                          "title": bool(p) and token_f1(p.title, g.title) >= 0.5,
                          "start": bool(p) and p.start == g.start,
                          "project": bool(p) and p.project == g.project,
                          "incomplete_flag": bool(p) and p.is_incomplete == g.is_incomplete}
                field_hits.update(k for k, v in checks.items() if v)
                ok = all(checks.values())
                item_ok += ok
                item_total += 1
                all_ok &= ok
            notes_ok += all_ok
            examples.append({"id": n.id, "ok": all_ok, "input": "asr" if n.id in asr else "gold_text", "text": text,
                             "pred": [(it.type, it.title, it.start, it.project) for it in res.items],
                             "gold": [(g.type, g.title, g.start, g.project) for g in n.items]})
            print(f"  e2e {n.id}: {'OK ' if all_ok else 'ERR'}")
    metrics = {"notes": len(examples), "input_audio_notes": sum(e["input"] == "asr" for e in examples),
               "notes_fully_correct": round(notes_ok / len(examples), 3),
               "items_fully_correct": round(item_ok / item_total, 3),
               "per_field_accuracy": {k: round(field_hits[k] / item_total, 3) for k in
                                      ["found", "type", "title", "start", "project", "incomplete_flag"]}}
    save(f"e2e_{source}", metrics, sorted(examples, key=lambda e: e["ok"]))


def eval_e2e_text() -> None:
    eval_e2e("text")


# ---------------------------------------------------------------- C9 daily brief
def eval_c9() -> None:
    """Gazette on 3 synthetic inboxes built from gold items (20 notes each, every 6th item marked done).
    Grounding (ids exist, no done items in today's agenda, no empty project dispatches, before the guards) and
    coverage (share of open items due today/overdue that make today's agenda; agenda is capped at 6)."""
    from datetime import date, timedelta

    from inbox import brief

    notes = load_gold()
    scenarios = []
    for k in range(3):
        chunk = notes[k * 20:(k + 1) * 20]
        today = date.fromisoformat(chunk[0].ref_time[:10]) + timedelta(days=k)
        items, n = [], 0
        for note in chunk:
            for gi in note.items:
                n += 1
                items.append({"id": n, "type": gi.type, "title": gi.title, "start": gi.start, "people": gi.people,
                              "project": gi.project, "is_incomplete": gi.is_incomplete,
                              "status": "done" if n % 6 == 0 else "open", "source_text": gi.title})
        scenarios.append((today, items))
    examples, agg = [], Counter()
    for today, items in scenarios:
        t0 = time.perf_counter()
        b = brief.generate(items, today)
        lat = time.perf_counter() - t0
        due = [it["id"] for it in items if it["status"] == "open" and it["start"] and it["start"][:10] <= today.isoformat()]
        got = {e.item_id for e in b.today}
        cov = len(got & set(due)) / min(6, len(due)) if due else 1.0
        rs = b.raw_stats
        agg.update(rs)
        agg["due"] += min(6, len(due))
        agg["due_hit"] += len(got & set(due))
        agg["latency"] += lat
        examples.append({"date": today.isoformat(), "items": len(items), "due": due, "today": sorted(got),
                         "coverage": round(cov, 2), "raw": rs, "headline": b.headline, "plan": b.plan,
                         "ok": cov >= 0.99 and not rs["invalid_ids"] and not rs["done_in_today"]})
    refs = max(agg["today_refs"], 1)
    metrics = {"inboxes": len(scenarios),
               "raw_invalid_id_rate": round(agg["invalid_ids"] / refs, 3),
               "raw_done_in_agenda_rate": round(agg["done_in_today"] / refs, 3),
               "raw_empty_dispatch_rate": round(agg["empty_dispatches"] / max(agg["dispatches"], 1), 3),
               "due_today_coverage": round(agg["due_hit"] / max(agg["due"], 1), 3),
               "avg_latency_s": round(agg["latency"] / len(scenarios), 1)}
    save("c9", metrics, examples, "Raw rates are before the rule guards; after the guards they are 0 by construction.")


COMPONENTS = {"c1": eval_c1, "c3": eval_c3, "c4": eval_c4, "c5": eval_c5, "c5_heldout": eval_c5_heldout,
              "c6": eval_c6, "c7": eval_c7, "c8": eval_c8, "c9": eval_c9, "e2e": eval_e2e, "e2e_text": eval_e2e_text}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", choices=sorted(COMPONENTS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore cached LLM predictions")
    args = ap.parse_args()
    targets = sorted(COMPONENTS) if args.all else [args.component]
    for c in targets:
        print(f"\n===== {c} =====")
        fn = COMPONENTS[c]
        fn(force=args.force) if "force" in fn.__code__.co_varnames else fn()


if __name__ == "__main__":
    main()
