"""Cached ``yt-dlp ytsearch`` lookups. No YouTube Data API, no key.

Live queries sleep (default 4 seconds) and are written into ``songcache.json``
under ``_queries``. A second call for the same phrase reads the file and does
not hit the network.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def search_command(query: str, n: int = 6) -> list[str]:
    return ["yt-dlp", "--flat-playlist", "-j", "--no-warnings", f"ytsearch{n}:{query}"]


def load_cache(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        return {"_queries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("_queries", {})
    return data


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def cached_search(
    query: str,
    path: Path,
    *,
    n: int = 6,
    runner=None,
    sleep_s: float = 4,
    sleeper=None,
) -> tuple[dict, bool]:
    """Return ``(payload, was_cached)``.

    ``payload`` is ``{"t": iso-ish timestamp, "res": [videos...]}``.
    """
    cache = load_cache(path)
    key = f"ytsearch{n}:{query}"
    queries = cache.setdefault("_queries", {})
    if key in queries:
        return queries[key], True
    if runner is None:
        from sermon_insights.catalog import default_runner

        runner = default_runner
    completed = runner(search_command(query, n))
    stdout = getattr(completed, "stdout", "") or ""
    results = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        results.append(
            {
                "title": item.get("title"),
                "channel": item.get("channel") or item.get("uploader"),
                "id": item.get("id"),
                "views": item.get("view_count"),
                "dur": item.get("duration"),
                "verified": item.get("channel_is_verified"),
            }
        )
    # Reload so a concurrent writer is not blindly overwritten.
    cache = load_cache(path)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    cache.setdefault("_queries", {})[key] = {"t": stamp, "res": results}
    save_cache(path, cache)
    if sleep_s and sleeper is not None:
        sleeper(sleep_s)
    elif sleep_s:
        time.sleep(sleep_s)
    return cache["_queries"][key], False
