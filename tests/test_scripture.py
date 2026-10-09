import json
from pathlib import Path

import pytest
import yaml

from sermon_insights.scripture import display_ref, find, get_index

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_snippet.json"


def test_exodus_snippet_normalises_to_english():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    text = " ".join(segment["text"] for segment in payload["segments"])
    hits = find(text)
    high = [hit for hit in hits if hit["ref"] == "Exodus 17:8-16"]
    assert high and high[0]["conf"] == "high"
    assert high[0]["book"] == "Exodus"
    assert high[0]["why"] == ""


@pytest.mark.parametrize(
    ("text", "ref", "conf"),
    [
        ("Mwanzo sura ya kwanza mstari wa kwanza", "Genesis 1:1", "high"),
        ("Zaburi 23", "Psalms 23", "medium"),
        ("zaburi sura ya 23 mstari wa kwanza", "Psalms 23:1", "high"),
        ("Wakorintho wa kwanza kifungu cha 13 mstari wa nne", "1 Corinthians 13:4", "high"),
        ("Wakorintho wa kwanza kifungu cha kumi na tatu mstari wa nne", "1 Corinthians 13:4", "high"),
        ("Zaburi sura ya ishirini na tatu mstari wa kwanza", "Psalms 23:1", "high"),
        ("Zaburi sura ya Ishirini na tatu mstari wa kwanza", "Psalms 23:1", "high"),
        ("Yohana sura ya 3 mstari wa 16", "John 3:16", "high"),
        ("John 3:16", "John 3:16", "high"),
        ("Marko 1:1", "Mark 1:1", "high"),
        ("Kutoka 20", "Exodus 20", "medium"),
        ("kitabu cha Isaya sura ya 43 mstari wa 16 hadi 21", "Isaiah 43:16-21", "high"),
        ("2 Samweli sura ya 6", "2 Samuel 6", "medium"),
        ("Luka 18:35-43", "Luke 18:35-43", "high"),
        ("Ufunuo", "Revelation", "low"),
        ("Psalms 119:177", "Psalms 119:177", "low"),
    ],
)
def test_book_normalisation(text, ref, conf):
    hits = find(text)
    assert hits, text
    assert hits[0]["ref"] == ref
    assert hits[0]["conf"] == conf


def test_bare_ambiguous_names_are_skipped():
    assert find("Mark alisema") == []
    assert find("Kutoka") == []
    assert find("Mwanzo") == []


def test_run_together_digits_are_marked_verify():
    hits = find("Exodus 1718")
    assert hits[0]["conf"] == "low"
    assert "verify" in hits[0]["why"]
    assert hits[0]["ref"] == "Exodus 17:18"
    assert display_ref(hits[0]["ref"], hits[0]["conf"]).endswith("(verify)")


def test_extra_language_map(tmp_path: Path):
    doc = {
        "language": "xx",
        "books": [{"name": "Genesis", "aliases": ["mwanzo-xx"], "ambiguous": False}],
        "bare_skip_aliases": [],
        "number_words": {"units": {"kwanza": 1}, "tens": {}, "hundred": None},
        "chapter_cues": ["sura"],
        "verse_cues": ["mstari"],
        "range_cues": ["hadi"],
    }
    (tmp_path / "xx.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    hits = find("mwanzo-xx sura 1 mstari kwanza", languages=["xx"], extra_dirs=[tmp_path])
    assert hits[0]["ref"] == "Genesis 1:1"
    assert hits[0]["conf"] == "high"


def test_swahili_map_lists_the_canon():
    index = get_index(["sw"])
    assert "Genesis" in index.order
    assert "Revelation" in index.order
    assert index.order.index("1 John") < index.order.index("2 John") < index.order.index("Jude")
