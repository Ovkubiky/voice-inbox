"""Download a few public-domain (CC0) landscape paintings from The Met Open Access API for the board's hero.

Saves inbox/web/art/<n>.jpg (resized to 1800 px wide with macOS `sips`) and inbox/web/art/art.json (credits).
Run once: uv run python scripts/fetch_art.py
"""

import json
import time
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "inbox" / "web" / "art"
API = "https://collectionapi.metmuseum.org/public/collection/v1"
_UNUSED_QUERIES = ["George Inness landscape", "Albert Bierstadt", "Thomas Cole landscape", "Jasper Cropsey",
           "Frederic Edwin Church", "Monet landscape", "Sanford Robinson Gifford", "Asher Brown Durand"]


def _json(c: httpx.Client, url: str, **params) -> dict:
    """Polite GET with retries: the Met API answers with an HTML error page when hit too fast."""
    for attempt in range(4):
        try:
            r = c.get(url, params=params or None)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(1.5 * (attempt + 1))
    return {}


# Hand-picked public-domain landscapes (Met object IDs); the search API returns few usable paintings.
OBJECT_IDS = [10497, 10481, 11230, 436535, 10158, 11234]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    credits = []
    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (voice-inbox student project)"}) as c:
        for oid in OBJECT_IDS:
            o = _json(c, f"{API}/objects/{oid}")
            if not (o.get("isPublicDomain") and o.get("primaryImage")):
                continue
            img = c.get(o["primaryImage"])
            if img.status_code != 200:
                continue
            n = len(credits) + 1
            path = OUT / f"{n}.jpg"
            path.write_bytes(img.content)
            subprocess.run(["sips", "--resampleWidth", "1800", "-s", "formatOptions", "78", str(path)],
                           check=False, capture_output=True)
            credits.append({"file": f"{n}.jpg", "title": o["title"], "artist": o["artistDisplayName"],
                            "date": o.get("objectDate", ""), "medium": o.get("medium", ""),
                            "source": o.get("objectURL", "")})
            print(f"  {n}. {o['artistDisplayName']} — {o['title']} ({o.get('objectDate')})")
            time.sleep(0.5)
    (OUT / "art.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {len(credits)} paintings to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
