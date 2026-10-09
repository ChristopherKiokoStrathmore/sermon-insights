"""Worship-song identification from lyric phrases.

Titles come from a local cache (``songcache.json``). A window of singing is
labelled only when a cached phrase is actually in the text. Confidence stays
at the cache's own level when at least two distinct phrases show up in at
least two 30-second windows. Anything thinner is downgraded, and a single
phrase in a single window is ``low`` and marked ``(verify)``. Over-common
chorus fragments in the stoplist never count.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from rapidfuzz import fuzz

WINDOW = 30
SPEECH = re.compile(
    r"\b(sifiwe|sifiiwe|sifiewe|mandiko|maandiko|kitabu|kitabucha|mstari|verse|"
    r"chapter|tuombe|naomba|tusome|mulango|mlango|bibile|biblia|tunaomba|amina|"
    r"asubui|asubuhi)\b"
)
TONGUE = re.compile(
    r"shalaba|shalabakanda|rababa|makanda|masika|imama|mazika|rekese|rikesa|"
    r"riki sike|rika rika|ramama|shakala|shara ma|masianda|mashandia"
)


def data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_stoplist(path: Path | None = None) -> set[str]:
    file = path or (data_dir() / "generic_phrases.txt")
    if not file.is_file():
        return set()
    return {line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()}


def load_hints(path: Path | None = None) -> list[tuple[str, str]]:
    file = path or (data_dir() / "lyric_hints.yaml")
    if not file.is_file():
        return []
    rows = yaml.safe_load(file.read_text(encoding="utf-8")) or []
    return [(row["pattern"], row["hint"]) for row in rows]


def despaced(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def song_rows(cache: dict) -> dict:
    return {key: value for key, value in cache.items() if not str(key).startswith("_")}


def confidence_for(n_distinct: int, n_windows: int, cache_confidence: str) -> str:
    """Keep, downgrade, or force-low a cache confidence.

    Two or more distinct phrases across two or more windows keep ``cache_confidence``.
    One phrase in one window is always ``low``. Every other thin match drops one level.
    """
    if n_distinct >= 2 and n_windows >= 2:
        return cache_confidence
    downgraded = {"high": "medium", "medium": "low", "low": "low"}.get(cache_confidence, "low")
    if n_distinct == 1 and n_windows == 1:
        return "low"
    return downgraded


def display_title(title: str | None, confidence: str) -> str:
    if not title:
        return "Unidentified"
    if confidence == "low" and "(verify)" not in title:
        return f"{title} (verify)"
    return title


def phrase_hits(text: str, cache: dict, stoplist: set[str] | None = None) -> dict[str, set[str]]:
    """Map song title -> matched phrase keys found in ``text``."""
    blocked = stoplist if stoplist is not None else load_stoplist()
    compact = despaced(text)
    found: dict[str, set[str]] = {}
    for title, meta in song_rows(cache).items():
        phrases: set[str] = set()
        keys = list(meta.get("keys") or []) + list(meta.get("wkeys") or [])
        for raw in keys:
            key = despaced(str(raw))
            if len(key) < 8 or key in blocked:
                continue
            if key in compact:
                phrases.add(key)
            elif (
                len(key) >= 14
                and len(compact) >= len(key)
                and fuzz.partial_ratio(key, compact) >= 90
            ):
                phrases.add(key)
        if phrases:
            found[title] = phrases
    return found


def _is_speech(text: str) -> bool:
    lowered = text.lower()
    words = re.findall(r"[a-z']+", lowered)
    if len(words) < 20:
        return False
    unique = len(set(words)) / len(words)
    markers = (
        len(SPEECH.findall(lowered))
        + lowered.count("sifiwe")
        + lowered.count("sifiiwe")
        + lowered.count("sifiewe")
    )
    return (unique > 0.6 and len(words) > 30) or (markers >= 2 and unique > 0.45) or markers >= 4


def _windows(
    segments: list[tuple[float, float, str]],
    duration_s: float,
    width: int,
) -> tuple[list[list[tuple[float, float, str]]], list[str]]:
    count = int(duration_s // width) + 1 if duration_s else 1
    buckets: list[list[tuple[float, float, str]]] = [[] for _ in range(count)]
    for start, end, text in segments:
        cleaned = text.strip()
        if not cleaned or re.fullmatch(r"[\d\s,.]+", cleaned):
            continue
        buckets[min(int(start // width), count - 1)].append((start, end, cleaned))
    texts = [" ".join(item[2] for item in bucket) for bucket in buckets]
    return buckets, texts


def _snippet(buckets, start_bin: int, end_bin: int, limit: int = 220) -> str:
    text = " ".join(item[2] for index in range(start_bin, end_bin) for item in buckets[index])
    text = re.sub(r"\s*>>\s*", " / ", text.replace("\n", " "))
    return text.strip(" /")[:limit]


def segment_worship(
    segments: list[tuple[float, float, str]],
    duration_s: float,
    cache: dict,
    *,
    stoplist: set[str] | None = None,
    hints: list[tuple[str, str]] | None = None,
    manual: list[tuple] | None = None,
    source_label: str = "Whisper transcript (medium, sw)",
    width: int = WINDOW,
) -> list[dict]:
    """Split a worship transcript into song blocks."""
    blocked = stoplist if stoplist is not None else load_stoplist()
    hint_rows = hints if hints is not None else load_hints()
    if duration_s <= 0 and segments:
        duration_s = max(segment[1] for segment in segments)
    buckets, texts = _windows(segments, duration_s, width)
    count = len(texts)
    kinds: list[str] = []
    labels: list[str | None] = []
    hits: list[dict[str, set[str]]] = []
    for text in texts:
        if not text.strip():
            kinds.append("empty")
            labels.append(None)
            hits.append({})
            continue
        if _is_speech(text):
            kinds.append("speech")
            labels.append(None)
            hits.append({})
            continue
        found = phrase_hits(text, cache, blocked)
        hits.append(found)
        kinds.append("music")
        labels.append(max(found, key=lambda title: len(found[title])) if found else None)

    for start_min, end_min, title in sorted(manual or [], key=lambda row: row[2] == "__SKIP__"):
        begin = int(float(start_min) * 60 // width)
        finish = min(count, int(-(-float(end_min) * 60 // width)))
        for index in range(begin, finish):
            if title == "__SKIP__":
                kinds[index] = "speech"
                labels[index] = None
                hits[index] = {}
                continue
            if kinds[index] == "empty":
                kinds[index] = "music"
            labels[index] = title or "__UNID__"

    for index in range(count):
        if labels[index] and labels[index] != "__UNID__":
            for gap in (2, 3):
                if (
                    index + gap < count
                    and labels[index + gap] == labels[index]
                    and all(
                        labels[cursor] is None and kinds[cursor] != "speech"
                        for cursor in range(index + 1, index + gap)
                    )
                ):
                    for cursor in range(index + 1, index + gap):
                        labels[cursor] = labels[index]

    blocks: list[list] = []
    index = 0
    while index < count:
        if kinds[index] in ("empty", "speech") and not labels[index]:
            index += 1
            continue
        if labels[index]:
            end = index
            while end < count and labels[end] == labels[index]:
                end += 1
            blocks.append([index, end, labels[index]])
            index = end
            continue
        words = set(re.findall(r"[a-z]+", texts[index].lower()))
        end = index + 1
        empty_run = 0
        while end < count and not labels[end] and kinds[end] != "speech":
            if kinds[end] == "empty":
                empty_run += 1
                if empty_run >= 2:
                    break
                end += 1
                continue
            other = set(re.findall(r"[a-z]+", texts[end].lower()))
            union = words | other
            jaccard = len(words & other) / max(1, len(union))
            if jaccard < 0.08 and end - index >= 3:
                break
            empty_run = 0
            words = other
            end += 1
        while end > index and kinds[end - 1] == "empty":
            end -= 1
        blocks.append([index, end, None])
        index = max(end, index + 1)

    songs = song_rows(cache)
    rows: list[dict] = []
    for start_bin, end_bin, label in blocks:
        word_count = sum(len(texts[cursor].split()) for cursor in range(start_bin, end_bin))
        start_s = min((item[0] for item in buckets[start_bin]), default=start_bin * width)
        end_s = max((item[1] for item in buckets[end_bin - 1]), default=end_bin * width)
        if label is None and (end_bin - start_bin) < 2 and word_count < 20:
            continue
        snippet = _snippet(buckets, start_bin, end_bin)
        if (
            label is None
            and len(TONGUE.findall(snippet.lower())) >= 2
            and not any(hits[cursor] for cursor in range(start_bin, end_bin))
        ):
            continue
        if label == "__UNID__":
            label = None
        if label:
            phrase_sets = [hits[cursor].get(label, set()) for cursor in range(start_bin, end_bin)]
            distinct: set[str] = set().union(*phrase_sets) if phrase_sets else set()
            n_windows = sum(1 for cursor in range(start_bin, end_bin) if label in hits[cursor])
            meta = songs.get(label, {})
            cache_conf = meta.get("conf") or "medium"
            hand = any(
                label == title and float(start_min) * 60 <= start_s + 1 < float(end_min) * 60 + 30
                for start_min, end_min, title in (manual or [])
            )
            confidence = cache_conf if hand else confidence_for(len(distinct), n_windows, cache_conf)
            method = (
                f"{source_label}; lyrics hand-checked against published lyrics"
                if hand
                else (
                    f"{source_label}; song-cache lyric match: {len(distinct)} key phrase(s) "
                    f"in {n_windows} of {end_bin - start_bin} 30-s window(s)"
                )
            )
            notes = meta.get("linknote") or ""
            if confidence == "low":
                notes = ("Weak match - verify. " + notes).strip()
            rows.append(
                {
                    "start_s": int(start_s),
                    "end_s": int(end_s),
                    "title": display_title(label, confidence),
                    "artist": meta.get("artist") or "",
                    "youtube": meta.get("link") or "",
                    "confidence": confidence,
                    "method": method,
                    "snippet": snippet,
                    "notes": notes,
                }
            )
            continue
        note = ""
        for pattern, hint in hint_rows:
            if re.search(pattern, snippet.lower()):
                note = "Lyrics heard (cleaned up): " + hint + " - title/artist not confirmed"
                break
        rows.append(
            {
                "start_s": int(start_s),
                "end_s": int(end_s),
                "title": "Unidentified",
                "artist": "",
                "youtube": "",
                "confidence": "low",
                "method": f"{source_label}; no confident lyric match",
                "snippet": snippet,
                "notes": note,
            }
        )
    if not rows:
        rows.append(
            {
                "start_s": 0,
                "end_s": int(duration_s),
                "title": "Unidentified",
                "artist": "",
                "youtube": "",
                "confidence": "low",
                "method": source_label,
                "snippet": "(almost no words in this transcript)",
                "notes": "Transcript nearly empty - songs could not be identified from lyrics",
            }
        )
    return rows
