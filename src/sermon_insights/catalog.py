"""Channel catalog via ``yt-dlp --flat-playlist``. No Data API key.

``/videos`` and ``/streams`` are both read. A file already in ``raw/`` is
parsed again and not downloaded again.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

SERMON_TITLE = re.compile(
    r"\bword\b|\bsermon\b|\bmahubiri\b|\bujumbe\b|\bservice\b|\bmessage\b|\bsunday\b|\bpreach\b|\bpastor\b",
    re.IGNORECASE,
)
WORSHIP_TITLE = re.compile(r"praise\s+and\s+worship|\bworship\b|\bsifa\b", re.IGNORECASE)
WORD_TITLE = re.compile(r"\bword\b", re.IGNORECASE)
NAMED_SERMON = re.compile(r"\bsermon\b|\bmahubiri\b|\bujumbe\b", re.IGNORECASE)


def default_runner(args: list[str]):
    return subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)


def channel_tab_urls(channel: str) -> tuple[str, str]:
    text = channel.strip().rstrip("/")
    if text.startswith("http://") or text.startswith("https://"):
        for suffix in ("/videos", "/streams", "/featured", "/shorts"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
        return text + "/videos", text + "/streams"
    handle = text if text.startswith("@") else f"@{text}"
    base = f"https://www.youtube.com/{handle}"
    return base + "/videos", base + "/streams"


def flat_playlist_command(url: str) -> list[str]:
    return ["yt-dlp", "--flat-playlist", "-J", "--no-warnings", url]


def parse_upload_date(entry: dict) -> date | None:
    raw = entry.get("upload_date")
    if raw:
        text = str(raw)
        if len(text) == 8 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d").date()
        if len(text) >= 10 and text[4] == "-":
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
    stamp = entry.get("timestamp") or entry.get("release_timestamp")
    if stamp:
        return datetime.fromtimestamp(int(stamp), UTC).date()
    return None


def is_public(entry: dict) -> bool:
    availability = (entry.get("availability") or "public").lower()
    if availability != "public":
        return False
    title = entry.get("title") or ""
    if title in ("[Private video]", "[Deleted video]"):
        return False
    return True


def likely_sermon(tab: str, duration, title: str, live_status: str | None, url: str) -> bool:
    live = tab == "streams" or live_status in ("was_live", "is_live", "post_live")
    short = "/shorts/" in (url or "") or (duration is not None and duration < 600)
    if live:
        return duration is not None and duration >= 1800
    return (not short) and duration is not None and duration >= 1500 and bool(SERMON_TITLE.search(title or ""))


def classify(title: str, tab: str, duration, live_status: str | None, url: str) -> str:
    text = title or ""
    if "praise and worship" in text.lower() or (
        WORSHIP_TITLE.search(text) and not WORD_TITLE.search(text)
    ):
        return "worship"
    if WORD_TITLE.search(text) or NAMED_SERMON.search(text):
        return "sermon"
    if likely_sermon(tab, duration, text, live_status, url):
        return "sermon"
    return "other"


def entry_row(entry: dict, tab: str) -> dict | None:
    video_id = entry.get("id")
    if not video_id:
        return None
    title = entry.get("title") or ""
    url = entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"
    if url.startswith("http") and "watch" not in url:
        url = f"https://www.youtube.com/watch?v={video_id}"
    duration = entry.get("duration")
    live_status = entry.get("live_status") or ("was_live" if tab == "streams" else None)
    kind = classify(title, tab, duration, live_status, url)
    return {
        "id": video_id,
        "title": title,
        "tab": tab,
        "upload_date": parse_upload_date(entry),
        "duration_s": int(duration) if duration is not None else None,
        "live_status": live_status,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "kind": kind,
        "likely_sermon": likely_sermon(tab, duration, title, live_status, url),
        "availability": (entry.get("availability") or "public"),
    }


def read_playlist(path: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("entries") or [])


def ensure_playlist(path: Path, url: str, *, runner, network: bool) -> list[dict]:
    """Return playlist entries, fetching with yt-dlp only when ``path`` is missing."""
    if path.is_file() and path.stat().st_size > 0:
        return read_playlist(path)
    if not network:
        return []
    completed = runner(flat_playlist_command(url))
    stdout = getattr(completed, "stdout", "") or ""
    if getattr(completed, "returncode", 1) != 0 or not stdout.strip():
        detail = (getattr(completed, "stderr", "") or "")[:400]
        raise RuntimeError(f"yt-dlp failed for {url}: {detail}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stdout, encoding="utf-8")
    return read_playlist(path)


def build_catalog(
    *,
    channel: str,
    since: date | None,
    raw_dir: Path,
    runner=None,
    network: bool = True,
) -> list[dict]:
    runner = runner or default_runner
    videos_url, streams_url = channel_tab_urls(channel)
    rows: list[dict] = []
    seen: set[str] = set()
    for tab, url in (("streams", streams_url), ("videos", videos_url)):
        entries = ensure_playlist(raw_dir / f"{tab}.json", url, runner=runner, network=network)
        for entry in entries:
            if not entry or not is_public(entry):
                continue
            row = entry_row(entry, tab)
            if row is None or row["id"] in seen:
                continue
            if since is not None and (row["upload_date"] is None or row["upload_date"] < since):
                continue
            if row["kind"] not in ("sermon", "worship"):
                continue
            seen.add(row["id"])
            rows.append(row)
    rows.sort(key=lambda row: (row["upload_date"] or date.min, row["id"]))
    return rows
