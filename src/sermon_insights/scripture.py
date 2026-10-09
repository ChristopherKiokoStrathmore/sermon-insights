"""Kiswahili-first scripture references, normalised to English book names.

The matcher is the one that grew up on real livestream captions: book aliases,
Swahili number words, chapter/verse cue words, and an explicit low-confidence
path for bare names, implausible numbers, and run-together digits. Weak hits
stay in the result with ``conf='low'`` and a reason; they are not dropped and
they are not upgraded.
"""

from __future__ import annotations

import re
from pathlib import Path

from sermon_insights.languages import load_map, merge_maps

_INDEXES: dict[tuple, ScriptureIndex] = {}


class ScriptureIndex:
    def __init__(self, languages: list[str] | None = None, extra_dirs: list[Path] | None = None):
        codes = list(languages or ["sw", "en"])
        merged = merge_maps([load_map(code, extra_dirs) for code in codes])
        self.order = merged["order"]
        self.order_index = {name: i for i, name in enumerate(self.order)}
        self.ambiguous = set(merged["ambiguous"])
        self.bare_skip = set(merged["bare_skip"])
        self.units = dict(merged["units"])
        self.tens = dict(merged["tens"])
        self.hundred = merged["hundred"]
        self.alias_map: dict[str, str] = {}
        pairs: list[tuple[str, str]] = []
        for book in self.order:
            for alias in merged["aliases"].get(book, []):
                pairs.append((alias, book))
        pairs.sort(key=lambda item: -len(item[0]))
        for alias, book in pairs:
            self.alias_map[alias] = book
        seen: list[str] = []
        for alias, _book in pairs:
            if alias not in seen:
                seen.append(alias)
        book_re = "|".join(re.escape(alias) for alias in seen)
        number_words = list(self.units) + list(self.tens)
        if self.hundred:
            number_words.append(self.hundred)
        number_words.append("na")
        num_re = "|".join(re.escape(word) for word in number_words)
        self._number = rf"(\d{{1,3}}|(?:(?:{num_re})\b\s*)+)"
        self._chapter = "(?:" + "|".join(merged["chapter_cues"]) + ")"
        self._verse = "(?:" + "|".join(merged["verse_cues"]) + ")"
        range_re = "(?:" + "|".join(merged["range_cues"]) + ")"
        self.pattern = re.compile(
            rf"\b(?:kitabu\s+cha\s+)?({book_re})\b[\s,]*"
            rf"(?:{self._chapter}\s+)?{self._number}?[\s,:.]*"
            rf"(?:{self._verse}\s+(?:ya\s+|wa\s+)?)?{self._number}?"
            rf"(?:\s*(?:{range_re})\s*(?:{self._verse}\s+(?:wa\s+)?)?{self._number})?",
            re.IGNORECASE,
        )

    def wnum(self, raw: str | None) -> int | None:
        """Parse digits or Swahili number words. Matching is case-insensitive.

        The earlier script compared number words in lowercase only, so a
        capitalised ``Ishirini`` was dropped and the following unit (``tatu``)
        was read as the whole number. Folding case keeps 23 as 23.
        """
        if raw is None:
            return None
        text = raw.strip()
        if text.isdigit():
            return int(text)
        total = 0
        ok = False
        for word in text.lower().split():
            if word == "na":
                continue
            if self.hundred and word == self.hundred:
                total += 100
                ok = True
            elif word in self.tens:
                total += self.tens[word]
                ok = True
            elif word in self.units:
                total += self.units[word]
                ok = True
        return total if ok else None

    def find(self, text: str) -> list[dict]:
        found: list[dict] = []
        if not text:
            return found
        for match in self.pattern.finditer(text):
            name = match.group(1).lower()
            book = self.alias_map.get(name)
            if book is None:
                continue
            chapter = self.wnum(match.group(2)) if match.group(2) else None
            verse = self.wnum(match.group(3)) if match.group(3) else None
            verse_end = self.wnum(match.group(4)) if match.group(4) else None
            span = match.group(0)
            explicit_chapter = bool(re.search(self._chapter, span, re.IGNORECASE)) or bool(
                match.group(2) and match.group(2).strip().isdigit()
            )
            explicit_verse = bool(re.search(self._verse, span, re.IGNORECASE)) or bool(
                match.group(3) and match.group(3).strip().isdigit()
            )
            if chapter is None:
                if book in self.ambiguous or name in self.bare_skip:
                    continue
                found.append(
                    {
                        "ref": book,
                        "book": book,
                        "conf": "low",
                        "why": "book only",
                        "span": span.strip(),
                    }
                )
                continue
            ref = f"{book} {chapter}"
            if verse:
                ref += f":{verse}"
                if verse_end and verse_end > verse:
                    ref += f"-{verse_end}"
            if explicit_chapter and explicit_verse and verse:
                confidence, why = "high", ""
            elif verse or explicit_chapter:
                confidence = "medium"
                why = (
                    "chapter only, no verse"
                    if not verse
                    else "chapter/verse not explicitly marked"
                )
            else:
                confidence, why = "low", "number may not be a chapter"
            if verse and verse > 176:
                confidence, why = "low", "implausible verse number"
            if chapter > 150 or (book != "Psalms" and chapter > 66):
                raw = (match.group(2) or "").strip()
                if raw.isdigit() and len(raw) in (3, 4):
                    chapter_guess = int(raw[:2])
                    verse_guess = int(raw[2:])
                    if verse:
                        verse_guess = int(raw[2:] + str(verse))
                    ref = f"{book} {chapter_guess}:{verse_guess}"
                    if verse_end and verse_end > verse_guess:
                        ref += f"-{verse_end}"
                    confidence = "low"
                    why = (
                        f'run-together digits "{raw}" read as {chapter_guess}:{verse_guess}'
                        " - verify (could also be a chapter range)"
                    )
                else:
                    confidence, why = "low", "implausible chapter"
            found.append(
                {
                    "ref": ref,
                    "book": book,
                    "conf": confidence,
                    "why": why,
                    "span": span.strip(),
                }
            )
        return found

    def sort_key(self, ref: str) -> tuple[int, int, int]:
        match = re.match(r"(.+?)(?: (\d+)(?::(\d+))?)?$", ref.strip())
        if not match:
            return (len(self.order) + 1, 0, 0)
        book = match.group(1)
        return (
            self.order_index.get(book, len(self.order) + 1),
            int(match.group(2) or 0),
            int(match.group(3) or 0),
        )


def get_index(
    languages: list[str] | None = None,
    extra_dirs: list[Path] | None = None,
) -> ScriptureIndex:
    codes = tuple(languages or ["sw", "en"])
    extra = tuple(str(path) for path in (extra_dirs or []))
    key = (codes, extra)
    if key not in _INDEXES:
        _INDEXES[key] = ScriptureIndex(list(codes), list(extra_dirs or []))
    return _INDEXES[key]


def find(
    text: str,
    languages: list[str] | None = None,
    extra_dirs: list[Path] | None = None,
) -> list[dict]:
    return get_index(languages, extra_dirs).find(text)


def display_ref(ref: str, confidence: str) -> str:
    """Low-confidence references stay visible and are marked for a human check."""
    if confidence == "low" and "(verify)" not in ref:
        return f"{ref} (verify)"
    return ref


def extract_timed(
    video_id: str,
    segments: list[tuple[float, float, str]],
    start_s: float,
    end_s: float,
    index: ScriptureIndex | None = None,
) -> list[dict]:
    """Find references inside a sermon span and attach timestamps.

    Adjacent caption lines are joined, because a cue sometimes starts on one
    line and the verse number lands on the next. The same reference inside
    three minutes is kept once. A bare book name is dropped when that book
    was already cited nearby.
    """
    index = index or get_index()
    window = [segment for segment in segments if start_s <= segment[0] <= end_s]
    if not window:
        return []
    pieces: list[tuple[int, float]] = []
    text = ""
    for start, _end, line in window:
        pieces.append((len(text), start))
        text += line.replace("\n", " ") + " "
    found: list[dict] = []
    for match in index.pattern.finditer(text):
        hits = index.find(match.group(0))
        if not hits:
            continue
        hit = dict(hits[0])
        timestamp = window[0][0]
        for offset, start in pieces:
            if offset <= match.start():
                timestamp = start
            else:
                break
        timestamp = int(timestamp)
        hit["ts"] = timestamp
        hit["link"] = f"https://www.youtube.com/watch?v={video_id}&t={timestamp}s"
        hit["snippet"] = text[max(0, match.start() - 120) : match.end() + 120].strip()
        if any(item["ref"] == hit["ref"] and abs(item["ts"] - timestamp) < 180 for item in found):
            continue
        if hit["why"] == "book only" and any(
            item["book"] == hit["book"] and abs(item["ts"] - timestamp) < 120 for item in found
        ):
            continue
        found.append(hit)
    return found


def guess_main_passage(
    segments: list[tuple[float, float, str]],
    start_s: float,
    end_s: float,
    refs: list[dict],
    index: ScriptureIndex | None = None,
) -> str:
    """First explicit reference in the opening quarter, else the most common one."""
    index = index or get_index()
    if end_s < start_s:
        end_s = start_s
    limit = start_s + (end_s - start_s) * 0.25
    for start, _end, line in segments:
        if start_s <= start <= min(end_s, limit):
            for hit in index.find(line):
                if hit["why"] != "book only":
                    return hit["ref"]
    counts: dict[str, int] = {}
    for hit in refs:
        if hit.get("why") == "book only":
            continue
        match = re.match(r"(.+? \d+)", hit["ref"])
        if not match:
            continue
        key = match.group(1)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]
