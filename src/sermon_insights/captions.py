"""Captions from youtube-transcript-api, then yt-dlp auto-subs.

Both paths are free and keyless. A video that already has a transcript or a
``subs/<id>.none`` marker is left alone. ``--force`` on the pipeline deletes
the marker so a video with no captions can be tried again; files that were
actually downloaded stay on disk.
"""

from __future__ import annotations

import time
from pathlib import Path

from sermon_insights.segments import write_transcript


def subtitle_command(video_id: str, out_dir: Path, sleep_requests: float, sleep_subtitles: float) -> list[str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    return [
        "yt-dlp",
        "--write-auto-subs",
        "--sub-langs",
        "sw-orig,en-orig",
        "--sub-format",
        "json3",
        "--skip-download",
        "--sleep-requests",
        str(sleep_requests),
        "--sleep-subtitles",
        str(sleep_subtitles),
        "--no-overwrites",
        "-o",
        str(out_dir / "%(id)s"),
        url,
    ]


def caption_paths(root: Path, video_id: str) -> dict[str, Path]:
    return {
        "transcript": root / "transcripts" / f"{video_id}.json",
        "sw": root / "subs" / f"{video_id}.sw-orig.json3",
        "en": root / "subs" / f"{video_id}.en-orig.json3",
        "none": root / "subs" / f"{video_id}.none",
    }


def already_captioned(root: Path, video_id: str) -> bool:
    paths = caption_paths(root, video_id)
    if any(paths[name].is_file() and paths[name].stat().st_size > 0 for name in ("transcript", "sw", "en", "none")):
        return True
    worship = root / "worship_transcripts" / f"{video_id}.json"
    return worship.is_file() and worship.stat().st_size > 0


def _language_source(code: str) -> tuple[str, str]:
    lowered = (code or "").lower()
    if lowered.startswith("sw"):
        return "sw", "yt-sw"
    return "en", "yt-en"


def fetch_api_transcript(video_id: str, languages: list[str], api=None):
    """Return ``(segments, language, source)`` or ``None`` when the API has nothing."""
    if api is None:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=languages)
    except Exception:
        return None
    snippets = list(fetched)
    if not snippets:
        return None
    segments = [
        (float(snippet.start), float(snippet.start) + float(snippet.duration or 0), snippet.text)
        for snippet in snippets
        if (snippet.text or "").strip()
    ]
    if not segments:
        return None
    language, source = _language_source(getattr(fetched, "language_code", "") or languages[0])
    return segments, language, source


def fetch_captions(
    root: Path,
    video_id: str,
    languages: list[str],
    *,
    api=None,
    runner=None,
    network: bool = True,
    sleep_requests: float = 2,
    sleep_subtitles: float = 6,
    sleeper=None,
    between_videos_s: float = 8,
) -> str:
    """Fetch captions for one public video. Return a short status string."""
    root = Path(root)
    if already_captioned(root, video_id):
        return "cached"
    if not network:
        return "skipped-offline"
    api_result = fetch_api_transcript(video_id, languages, api=api)
    if api_result:
        segments, language, source = api_result
        write_transcript(
            root / "transcripts" / f"{video_id}.json",
            video_id,
            segments,
            language=language,
            source=source,
        )
        if between_videos_s:
            (sleeper or time.sleep)(between_videos_s)
        return f"api-{source}"
    if runner is None:
        from sermon_insights.catalog import default_runner

        runner = default_runner
    subs = root / "subs"
    subs.mkdir(parents=True, exist_ok=True)
    completed = runner(subtitle_command(video_id, subs, sleep_requests, sleep_subtitles))
    sw = subs / f"{video_id}.sw-orig.json3"
    en = subs / f"{video_id}.en-orig.json3"
    if sw.is_file() or en.is_file():
        if between_videos_s:
            (sleeper or time.sleep)(between_videos_s)
        return "yt-dlp-subs"
    if getattr(completed, "returncode", 1) == 0:
        (subs / f"{video_id}.none").write_text("no auto-captions\n", encoding="utf-8")
        return "none"
    return "failed"
