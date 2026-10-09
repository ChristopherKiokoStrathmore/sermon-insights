"""Write the tiny offline fixture. Synthetic text only: no channel, no preacher."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "samples" / "offline" / "fixture"
SEED = ROOT / "src" / "sermon_insights" / "data" / "songcache.seed.json"

SERMON_ID = "FixSermon1a"
WORSHIP_ID = "FixWorship1"


def _alpha(n: int) -> str:
    """Letter-only filler. Digit tokens are split by the speech-word regex and look repetitive."""
    chars: list[str] = []
    value = n + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("a") + remainder))
    return "w" + "".join(reversed(chars))


def bin_text(index: int, sentence: str) -> str:
    padding = " ".join(_alpha(index * 40 + n) for n in range(32))
    body = sentence.strip()
    if body and body[-1] not in ".!?":
        body += "."
    # Filler is its own sentence so extractive summary ranks the spoken lines.
    return f"{body} {padding}."


def sermon_segments() -> list[dict]:
    sentences = {
        0: (
            "Tufungue biblia. Tusome Wakorintho wa kwanza kifungu cha kumi na tatu "
            "mstari wa nne. Upendo huvumilia. Familia inajengwa kwa upendo. "
            "Upendo hujenga familia na ndoa, na ndoa inasimama pale upendo unapobaki. "
            "Leo tunasoma jinsi upendo unavyolinda familia, na jinsi ndoa inavyohitaji "
            "upendo kila siku. Hii ndiyo neno la leo kwa kila familia inayosikiliza."
        ),
        2: "Upendo hujenga familia na ndoa. Love bears all things in a family.",
        4: "Upendo wa familia unalinda ndoa. Love keeps a family together.",
        6: "Familia inahitaji upendo na ndoa inahitaji upendo.",
        8: (
            "Zaburi sura ya ishirini na tatu mstari wa kwanza. "
            "Bwana ndiye mchungaji wangu na upendo wake ni wa milele."
        ),
        10: "Upendo ndio ujumbe wa familia. Love is the message for a family.",
        14: "Ndoa inasimama kwa upendo. A family stands when love stays.",
        21: "Tuombe sasa. Upendo na familia vinaendelea.",
    }
    rows = []
    for index in range(22):
        sentence = sentences.get(index, "Upendo unajenga familia siku hii.")
        start = index * 60
        rows.append({"start": start, "end": start + 50, "text": bin_text(index, sentence)})
    return rows


def worship_segments() -> list[dict]:
    chorus = "wewe uongezeke mimi nipungue uongezeke yesu uongezeke sana " * 4
    rows = []
    for start in range(0, 90, 10):
        rows.append({"start": start, "end": start + 9, "text": chorus.strip()})
    rows.append({"start": 200, "end": 220, "text": "nje ya lango nje ya lango"})
    la = "lalala lalala lalala lalala lalala lalala " * 3
    for start in (300, 320, 340, 360):
        rows.append({"start": start, "end": start + 15, "text": la.strip()})
    return rows


def songcache() -> dict:
    return {
        "Uongezeke Yesu": {
            "artist": "Boaz Danken",
            "conf": "high",
            "keys": ["wewe uongezeke", "mimi nipungue", "uongezeke yesu", "uongezeke sana"],
            "wkeys": [],
            "link": "https://www.youtube.com/watch?v=YG7ajzYyE1I",
            "linknote": "Published worship song. Official video on the artist's channel.",
            "source": "fixture seed",
        },
        "Nje ya Lango": {
            "artist": "Florence Mureithi",
            "conf": "high",
            "keys": ["nje ya lango"],
            "wkeys": [],
            "link": "https://www.youtube.com/watch?v=jUZ0YrQB2EA",
            "linknote": "Published worship song.",
            "source": "fixture seed",
        },
        "_queries": {},
    }


def main() -> None:
    FIXTURE.mkdir(parents=True, exist_ok=True)
    (FIXTURE / "raw").mkdir(exist_ok=True)
    (FIXTURE / "transcripts").mkdir(exist_ok=True)
    (FIXTURE / "worship_transcripts").mkdir(exist_ok=True)
    streams = {
        "id": "fixture-streams",
        "entries": [
            {
                "id": SERMON_ID,
                "title": "WORD || 15 JUNE 2025",
                "duration": 1320,
                "upload_date": "20250615",
                "live_status": "was_live",
                "availability": "public",
                "url": f"https://www.youtube.com/watch?v={SERMON_ID}",
            },
            {
                "id": WORSHIP_ID,
                "title": "PRAISE AND WORSHIP || 15 JUNE 2025",
                "duration": 400,
                "upload_date": "20250615",
                "live_status": "was_live",
                "availability": "public",
                "url": f"https://www.youtube.com/watch?v={WORSHIP_ID}",
            },
            {
                "id": "OldSermon01",
                "title": "WORD || 01 DEC 2024",
                "duration": 1800,
                "upload_date": "20241201",
                "live_status": "was_live",
                "availability": "public",
            },
            {
                "id": "PrivateVid1",
                "title": "[Private video]",
                "duration": 1800,
                "upload_date": "20250601",
                "availability": "private",
                "live_status": "was_live",
            },
        ],
    }
    (FIXTURE / "raw" / "streams.json").write_text(json.dumps(streams, indent=1) + "\n", encoding="utf-8")
    (FIXTURE / "raw" / "videos.json").write_text(
        json.dumps({"id": "fixture-videos", "entries": []}, indent=1) + "\n",
        encoding="utf-8",
    )
    sermon = {
        "id": SERMON_ID,
        "language": "sw",
        "model": "medium",
        "source": "whisper-sw",
        "duration": 1320,
        "segments": sermon_segments(),
    }
    worship = {
        "id": WORSHIP_ID,
        "language": "sw",
        "model": "medium",
        "source": "whisper-sw",
        "duration": 400,
        "segments": worship_segments(),
    }
    (FIXTURE / "transcripts" / f"{SERMON_ID}.json").write_text(
        json.dumps(sermon, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (FIXTURE / "worship_transcripts" / f"{WORSHIP_ID}.json").write_text(
        json.dumps(worship, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cache = songcache()
    (FIXTURE / "songcache.json").write_text(
        json.dumps(cache, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    SEED.parent.mkdir(parents=True, exist_ok=True)
    SEED.write_text(json.dumps(cache, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    snippet_src = Path("/tmp/sermon-bundle/samples/transcript_snippet.json")
    dest = ROOT / "tests" / "fixtures" / "transcript_snippet.json"
    if snippet_src.is_file():
        snippet = json.loads(snippet_src.read_text(encoding="utf-8"))
        snippet["id"] = "fixture-exodus"
        snippet.pop("_note", None)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(snippet, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fixture written under {FIXTURE}")


if __name__ == "__main__":
    main()
