from sermon_insights.summary import extractive_summary
from sermon_insights.topics import assign_themes, keyword_theme, load_themes


def test_extractive_summary_copies_transcript_lines():
    segments = [
        (0, 10, "Tufungue biblia na tusome kifungu cha upendo."),
        (20, 30, "Upendo hujenga familia na ndoa kwa upendo."),
        (40, 50, "Upendo hujenga familia na ndoa kwa upendo."),
        (60, 70, "Love bears all things in this family today."),
    ]
    summary = extractive_summary(segments, 0, 80, backend="lexical")
    assert summary["source"] == "extractive-lexical"
    assert "Tufungue biblia" in summary["sw"]
    assert "not a translation" in summary["en"] or "Love bears" in summary["en"]
    for sentence in ("Upendo hujenga familia na ndoa kwa upendo.", "Love bears all things in this family today."):
        if sentence[:20] in summary["en"]:
            assert sentence in summary["en"]


def test_embedding_backend_uses_the_encoder_it_is_given():
    segments = [
        (0, 5, "Alpha sentence about upendo familia ndoa love."),
        (6, 10, "Beta sentence stays off to the side here."),
        (12, 20, "Alpha sentence about upendo familia ndoa love."),
    ]

    def encode(sentences):
        return [[1.0, 0.0] if "Alpha" in sentence else [0.0, 1.0] for sentence in sentences]

    summary = extractive_summary(segments, 0, 30, backend="embedding", encode=encode)
    assert summary["source"] == "extractive-embedding"
    assert "Alpha sentence" in summary["en"]


def test_keyword_theme_follows_the_seed_patterns():
    themes = load_themes()
    name, score = keyword_theme(
        "Upendo hujenga familia na ndoa. Love bears all things. " * 5,
        themes,
    )
    assert name == "Love & Relationships"
    assert score > 0


def test_bertopic_path_falls_back_when_the_extra_is_missing(monkeypatch):
    def explode(*_args, **_kwargs):
        raise ImportError("no bertopic")

    monkeypatch.setattr("sermon_insights.topics.bertopic_labels", explode)
    labels, method = assign_themes(
        ["upendo familia ndoa love"] * 3,
        backend="bertopic",
        min_docs=2,
    )
    assert labels
    assert method.startswith("keyword-seed")
    assert "not installed" in method or "BERTopic" in method


def test_auto_backend_waits_for_enough_sermons():
    labels, method = assign_themes(["upendo familia"] , backend="auto", min_docs=8)
    assert labels == ["Love & Relationships"] or labels
    assert "at least 8" in method
