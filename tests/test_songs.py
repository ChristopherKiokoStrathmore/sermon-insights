from sermon_insights.songs import confidence_for, display_title, phrase_hits, segment_worship

CACHE = {
    "Uongezeke Yesu": {
        "artist": "Boaz Danken",
        "conf": "high",
        "keys": ["wewe uongezeke", "mimi nipungue", "uongezeke yesu"],
        "link": "https://www.youtube.com/watch?v=YG7ajzYyE1I",
        "linknote": "published",
    },
    "Shangilia": {
        "artist": "Example",
        "conf": "high",
        "keys": ["piga kelele kwa bwana"],
        "wkeys": ["ametukuka"],
        "link": "",
    },
}
STOP = {"ametukuka", "mataifayote"}


def test_confidence_rules():
    assert confidence_for(2, 2, "high") == "high"
    assert confidence_for(3, 4, "medium") == "medium"
    assert confidence_for(1, 1, "high") == "low"
    assert confidence_for(2, 1, "high") == "medium"
    assert confidence_for(1, 3, "high") == "medium"
    assert confidence_for(1, 1, "low") == "low"
    assert display_title("Uongezeke Yesu", "low") == "Uongezeke Yesu (verify)"
    assert display_title("Uongezeke Yesu", "high") == "Uongezeke Yesu"


def test_stoplist_blocks_generic_phrases():
    hits = phrase_hits("ametukuka milele ametukuka", CACHE, STOP)
    assert "Shangilia" not in hits


def test_fuzzy_phrase_counts_when_it_is_long_enough():
    cache = {
        "Be Lifted": {
            "conf": "high",
            "keys": ["we lay our crowns down"],
            "wkeys": [],
        }
    }
    heard = "we lay our crowns down now"
    assert "Be Lifted" in phrase_hits(heard, cache, set())
    typo = "we lay our crownz down tonight in worship"
    assert "Be Lifted" in phrase_hits(typo, cache, set())


def test_two_windows_keep_cache_confidence_and_one_window_is_verify():
    chorus = "wewe uongezeke mimi nipungue uongezeke yesu " * 3
    segments = []
    for start in range(0, 70, 10):
        segments.append((start, start + 9, chorus))
    segments.append((200, 215, "nje ya lango"))
    cache = dict(CACHE)
    cache["Nje ya Lango"] = {"artist": "Florence Mureithi", "conf": "high", "keys": ["nje ya lango"]}
    rows = segment_worship(segments, 240, cache, stoplist=STOP, hints=[], source_label="fixture")
    strong = [row for row in rows if row["title"] == "Uongezeke Yesu"]
    weak = [row for row in rows if "Nje ya Lango" in row["title"]]
    assert strong and strong[0]["confidence"] == "high"
    assert "(verify)" not in strong[0]["title"]
    assert weak and weak[0]["confidence"] == "low"
    assert weak[0]["title"].endswith("(verify)")
    assert "verify" in weak[0]["notes"].lower()
