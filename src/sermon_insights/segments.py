"""Read timed lines from whisper JSON or YouTube json3 captions.

Swahili auto-captions win over a whisper file when both exist. That preference
came from comparing the two on the same livestreams: ``sw-orig`` tracked the
preacher more closely than a second transcription pass.
"""

from __future__ import annotations

import json
from pathlib import Path


def from_whisper_payload(payload: dict) -> tuple[list[tuple[float, float, str]], str]:
    segments = [
        (float(row["start"]), float(row["end"]), row.get("text") or "")
        for row in payload.get("segments") or []
        if (row.get("text") or "").strip()
    ]
    source = payload.get("source") or f"whisper-{payload.get('language', '?')}"
    return segments, source


def from_json3(payload: dict, source: str) -> tuple[list[tuple[float, float, str]], str]:
    rows = []
    for event in payload.get("events") or []:
        text = "".join(piece.get("utf8", "") for piece in event.get("segs") or []).strip()
        if not text:
            continue
        start = event["tStartMs"] / 1000
        duration = event.get("dDurationMs", 2000) / 1000
        rows.append((start, start + duration, text))
    return rows, source


def load_named(path: Path) -> tuple[list[tuple[float, float, str]], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "events" in payload and "segments" not in payload:
        return from_json3(payload, path.stem)
    return from_whisper_payload(payload)


def load_segments(root: Path, video_id: str, *, worship: bool = False):
    """Return ``(segments, source, meta)``. ``source`` is ``None`` when nothing is on disk."""
    root = Path(root)
    if worship:
        worship_path = root / "worship_transcripts" / f"{video_id}.json"
        if worship_path.is_file():
            payload = json.loads(worship_path.read_text(encoding="utf-8"))
            segments, source = from_whisper_payload(payload)
            if not str(source).startswith("whisper"):
                source = payload.get("source") or f"whisper-{payload.get('language', 'sw')}"
            return segments, source, payload
    sw_caption = root / "subs" / f"{video_id}.sw-orig.json3"
    transcript = root / "transcripts" / f"{video_id}.json"
    if sw_caption.is_file():
        payload = json.loads(sw_caption.read_text(encoding="utf-8"))
        segments, source = from_json3(payload, "yt-sw-orig")
        return segments, source, payload
    if transcript.is_file():
        payload = json.loads(transcript.read_text(encoding="utf-8"))
        segments, source = from_whisper_payload(payload)
        return segments, source, payload
    en_caption = root / "subs" / f"{video_id}.en-orig.json3"
    if en_caption.is_file():
        payload = json.loads(en_caption.read_text(encoding="utf-8"))
        segments, source = from_json3(payload, "yt-en-orig")
        return segments, source, payload
    if worship:
        return load_segments(root, video_id, worship=False)
    return [], None, {}


def write_transcript(path: Path, video_id: str, segments, *, language: str, source: str, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": video_id,
        "language": language,
        "source": source,
        "segments": [
            {"start": float(start), "end": float(end), "text": text}
            for start, end, text in segments
        ],
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
