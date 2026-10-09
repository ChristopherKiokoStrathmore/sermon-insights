"""Sermon-span detection from timed transcript lines.

A minute is treated as speech when it has enough words, enough lexical variety,
and no music tags. The longest speech run is kept, short gaps included, and
the edges are pulled toward Kiswahili or English cues ("tufungue biblia",
"tuombe") when those cues sit near the run.
"""

from __future__ import annotations

import re

BIN_SECONDS = 60
CUE_START = re.compile(
    r"tufungue|fungua(ni)? biblia|somo la leo|neno la mungu|neno la leo|"
    r"ujumbe wa leo|tusome|turn (with me )?to|open your bible|the word of god|"
    r"let us read|kitabu cha|our text|message (of|for) today|mahubiri",
    re.IGNORECASE,
)
CUE_END = re.compile(
    r"tuombe|let us pray|let's pray|simama|stand up|tusimame|nyosha mikono|"
    r"altar|wokovu|okoka",
    re.IGNORECASE,
)
_MUSIC = re.compile(r"\[(music|muziki|muzik)\]|♪", re.IGNORECASE)


def _bins(
    segments: list[tuple[float, float, str]],
    duration_s: float,
    bin_s: int,
) -> list[dict]:
    count = int(duration_s // bin_s) + 1
    texts = [""] * count
    for start, _end, text in segments:
        index = min(int(start // bin_s), count - 1)
        texts[index] += " " + text
    feats = []
    for text in texts:
        words = re.findall(r"[a-zA-Z']+", text.lower())
        word_count = len(words)
        unique = len(set(words)) / word_count if word_count else 0
        music = len(_MUSIC.findall(text))
        feats.append({"wc": word_count, "uniq": unique, "music": music, "text": text})
    return feats


def detect_span(
    segments: list[tuple[float, float, str]],
    duration_s: float,
    *,
    source: str = "transcript",
    min_words: int = 25,
    gap_bins: int = 3,
    max_music: int = 0,
    bin_s: int = BIN_SECONDS,
) -> dict:
    """Return the sermon window, or a ``confidence='none'`` result."""
    if not segments:
        return {
            "sermon_start_s": None,
            "sermon_end_s": None,
            "method": f"{source}:speech-run",
            "confidence": "none",
            "source": source,
            "note": "no transcript",
        }
    feats = _bins(segments, duration_s, bin_s)
    speech = [
        item["wc"] >= min_words and item["uniq"] >= 0.42 and item["music"] <= max_music
        for item in feats
    ]
    best = (0, 0)
    run_start = None
    gap = 0
    last = None
    for index, is_speech in enumerate(speech + [False] * (gap_bins + 2)):
        if is_speech:
            if run_start is None:
                run_start = index
            last = index
            gap = 0
        elif run_start is not None:
            gap += 1
            if gap > gap_bins:
                if last - run_start > best[1] - best[0]:
                    best = (run_start, last)
                run_start = None
                gap = 0
    first, last_bin = best
    if last_bin - first < 10:
        return {
            "sermon_start_s": None,
            "sermon_end_s": None,
            "method": f"{source}:speech-run",
            "confidence": "none",
            "source": source,
            "note": "no >=10min continuous speech run",
        }
    start_s = first * bin_s
    end_s = (last_bin + 1) * bin_s
    start_cues = [
        segment[0]
        for segment in segments
        if start_s - 300 <= segment[0] <= start_s + 300 and CUE_START.search(segment[2])
    ]
    end_cues = [
        segment[0]
        for segment in segments
        if end_s - 420 <= segment[0] <= end_s + 120 and CUE_END.search(segment[2])
    ]
    method = f"{source}:speech-run"
    if start_cues:
        start_s = int(min(start_cues, key=lambda timestamp: abs(timestamp - start_s)))
        method += "+start-cue"
    if end_cues:
        end_s = int(max(end_cues))
        method += "+end-cue"
    end_s = int(min(end_s, duration_s))
    start_s = int(max(0, start_s))
    length_min = (end_s - start_s) / 60
    fraction = sum(speech[first : last_bin + 1]) / (last_bin - first + 1)
    sw_or_whisper = source.startswith(("yt-sw", "whisper"))
    if length_min >= 20 and fraction >= 0.85 and start_cues and sw_or_whisper:
        confidence = "high"
    elif length_min >= 15 and fraction >= 0.7:
        confidence = "medium"
    else:
        confidence = "low"
    return {
        "sermon_start_s": start_s,
        "sermon_end_s": end_s,
        "method": method,
        "confidence": confidence,
        "source": source,
        "note": f"run {length_min:.0f}min speechfrac {fraction:.2f}",
    }
