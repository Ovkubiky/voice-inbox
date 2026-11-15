"""Shared metric helpers for all component evals."""

import re
from collections import Counter

STOP = {"і", "й", "та", "а", "в", "у", "з", "із", "зі", "на", "до", "по", "про", "щодо", "для", "від", "за", "о",
        "що", "це", "треба", "ще", "не", "так", "ну", "мені", "нагадай", "забути"}


def stems(text: str | None) -> set[str]:
    """Crude Ukrainian stemming: lowercase, drop stopwords, keep the first 5 letters (handles inflection)."""
    tokens = re.findall(r"[\w']+", (text or "").lower().replace("’", "'"))
    return {t[:5] for t in tokens if t not in STOP}


def token_f1(pred: str | None, gold: str | None) -> float:
    p, g = stems(pred), stems(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    tp = len(p & g)
    if tp == 0:
        return 0.0
    prec, rec = tp / len(p), tp / len(g)
    return 2 * prec * rec / (prec + rec)


def set_f1(pred: list[str], gold: list[str]) -> float:
    p, g = {x.lower()[:4] for x in pred}, {x.lower()[:4] for x in gold}
    if not p and not g:
        return 1.0
    tp = len(p & g)
    if tp == 0:
        return 0.0
    prec, rec = tp / len(p), tp / len(g)
    return 2 * prec * rec / (prec + rec)


def align(preds: list[str], golds: list[str], threshold: float = 0.25) -> list[tuple[int, int]]:
    """Greedy one-to-one alignment of predicted to gold items by stemmed token F1."""
    pairs = sorted(((token_f1(p, g), i, j) for i, p in enumerate(preds) for j, g in enumerate(golds)), reverse=True)
    used_p, used_g, out = set(), set(), []
    for score, i, j in pairs:
        if score < threshold or i in used_p or j in used_g:
            continue
        used_p.add(i), used_g.add(j), out.append((i, j))
    return sorted(out, key=lambda x: x[1])


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def macro_f1(pairs: list[tuple[str, str]], labels: list[str]) -> tuple[float, dict]:
    """pairs = (pred, gold). Returns macro-F1 and per-label F1."""
    per = {}
    for lab in labels:
        tp = sum(1 for p, g in pairs if p == lab and g == lab)
        fp = sum(1 for p, g in pairs if p == lab and g != lab)
        fn = sum(1 for p, g in pairs if p != lab and g == lab)
        per[lab] = prf(tp, fp, fn)["f1"]
    present = [lab for lab in labels if any(g == lab for _, g in pairs)]
    return round(sum(per[l] for l in present) / max(len(present), 1), 3), per


def confusion(pairs: list[tuple[str, str]], labels: list[str]) -> str:
    c = Counter(pairs)
    head = "| gold \\ pred | " + " | ".join(labels) + " |\n|" + "---|" * (len(labels) + 1) + "\n"
    rows = "".join(f"| **{g}** | " + " | ".join(str(c[(p, g)]) for p in labels) + " |\n" for g in labels)
    return head + rows
