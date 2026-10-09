"""Load and merge per-language scripture book maps."""

from __future__ import annotations

from pathlib import Path

import yaml


def bundled_language_dir() -> Path:
    return Path(__file__).resolve().parent / "languages"


def load_map(code: str, extra_dirs: list[Path] | None = None) -> dict:
    """Return the parsed map for ``code`` (``sw``, ``en``, or a plugin code)."""
    search = [*(extra_dirs or []), bundled_language_dir()]
    for directory in search:
        path = Path(directory) / f"{code}.yaml"
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if "books" not in data:
                raise ValueError(f"{path} has no 'books' list")
            data["language"] = data.get("language") or code
            return data
    searched = ", ".join(str(Path(d) / f"{code}.yaml") for d in search)
    raise FileNotFoundError(
        f"No scripture map for language {code!r}. Looked for: {searched}. "
        "Add a YAML file; see CONTRIBUTING.md."
    )


def merge_maps(maps: list[dict]) -> dict:
    """Merge maps. Earlier languages win book order and number-word clashes.

    Aliases and cue fragments are unions, so adding ``en`` beside ``sw`` does
    not drop Kiswahili forms.
    """
    if not maps:
        raise ValueError("at least one language map is required")
    aliases: dict[str, list[str]] = {}
    ambiguous: set[str] = set()
    order: list[str] = []
    units: dict[str, int] = {}
    tens: dict[str, int] = {}
    hundred: str | None = None
    bare: list[str] = []
    chapter: list[str] = []
    verse: list[str] = []
    ranges: list[str] = []

    def _extend_unique(bucket: list[str], items: list[str]) -> None:
        for item in items:
            if item not in bucket:
                bucket.append(item)

    for doc in maps:
        for book in doc.get("books") or []:
            name = book["name"]
            if name not in aliases:
                aliases[name] = []
                order.append(name)
            for alias in book.get("aliases") or []:
                key = str(alias).strip().lower()
                if key and key not in aliases[name]:
                    aliases[name].append(key)
            if book.get("ambiguous"):
                ambiguous.add(name)
        _extend_unique(bare, [str(a).lower() for a in doc.get("bare_skip_aliases") or []])
        words = doc.get("number_words") or {}
        for key, value in (words.get("units") or {}).items():
            units.setdefault(str(key).lower(), int(value))
        for key, value in (words.get("tens") or {}).items():
            tens.setdefault(str(key).lower(), int(value))
        if hundred is None and words.get("hundred"):
            hundred = str(words["hundred"]).lower()
        _extend_unique(chapter, [str(c) for c in doc.get("chapter_cues") or []])
        _extend_unique(verse, [str(c) for c in doc.get("verse_cues") or []])
        _extend_unique(ranges, [str(c) for c in doc.get("range_cues") or []])

    return {
        "order": order,
        "aliases": aliases,
        "ambiguous": ambiguous,
        "bare_skip": set(bare),
        "units": units,
        "tens": tens,
        "hundred": hundred,
        "chapter_cues": chapter,
        "verse_cues": verse,
        "range_cues": ranges,
    }
