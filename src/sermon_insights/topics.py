"""Broad themes for sermons and the verses quoted inside them.

Keyword patterns are the seed (and the fallback). When ``backend`` is
``bertopic`` or ``auto`` with enough sermons, titles come from BERTopic
guided by those seed words and a multilingual sentence-transformer.
Fewer sermons than ``min_docs``, or a missing extra, stay on the keyword
seed. The method string says which path ran.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


def load_themes(path: Path | None = None) -> list[dict]:
    file = path or Path(__file__).resolve().parent / "data" / "themes.yaml"
    return yaml.safe_load(file.read_text(encoding="utf-8")) or []


def keyword_theme(text: str, themes: list[dict] | None = None) -> tuple[str, float]:
    themes = themes if themes is not None else load_themes()
    lowered = text.lower()
    word_count = max(1, len(lowered.split()))
    scores = {}
    for theme in themes:
        hits = len(re.findall(theme["pattern"], lowered))
        scores[theme["name"]] = hits * 1000 / word_count
    if not scores or max(scores.values()) <= 0:
        return "Unclassified", 0.0
    name = max(scores, key=scores.get)
    return name, scores[name]


def _closest_seed(words: list[str], themes: list[dict]) -> str:
    bag = {word.lower() for word in words}
    best_name = "Unclassified"
    best_score = 0
    for theme in themes:
        seeds = {seed.lower() for seed in theme.get("seeds") or []}
        score = len(bag & seeds)
        if score > best_score:
            best_score = score
            best_name = theme["name"]
    return best_name


def bertopic_labels(
    documents: list[str],
    themes: list[dict],
    model_name: str,
) -> list[str]:
    """Cluster ``documents`` with BERTopic. Raises ImportError if the extra is absent."""
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(model_name)
    seeds = [list(theme.get("seeds") or []) for theme in themes]
    model = BERTopic(
        embedding_model=embedder,
        seed_topic_list=seeds or None,
        min_topic_size=2,
        verbose=False,
        calculate_probabilities=False,
    )
    topic_ids, _probs = model.fit_transform(documents)
    names: dict[int, str] = {}
    for topic_id in set(topic_ids):
        if topic_id == -1:
            continue
        topic = model.get_topic(topic_id) or []
        words = [word for word, _score in topic]
        names[int(topic_id)] = _closest_seed(words, themes)
    labels = []
    for index, topic_id in enumerate(topic_ids):
        if topic_id == -1 or int(topic_id) not in names or names[int(topic_id)] == "Unclassified":
            labels.append(keyword_theme(documents[index], themes)[0])
        else:
            labels.append(names[int(topic_id)])
    return labels


def assign_themes(
    documents: list[str],
    *,
    backend: str = "auto",
    min_docs: int = 8,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    themes: list[dict] | None = None,
) -> tuple[list[str], str]:
    """Return ``(labels, method)``.

    ``method`` is ``bertopic-seed`` only when BERTopic actually fit the
    documents. Every other path is a ``keyword-seed`` label that says why.
    """
    themes = themes if themes is not None else load_themes()
    keyword_labels = [keyword_theme(text, themes)[0] for text in documents]
    if backend == "keyword":
        return keyword_labels, "keyword-seed"
    if len(documents) < min_docs and backend != "bertopic":
        return (
            keyword_labels,
            f"keyword-seed (BERTopic waits for at least {min_docs} sermons; this run has {len(documents)})",
        )
    try:
        labels = bertopic_labels(documents, themes, model_name)
    except ImportError:
        return keyword_labels, "keyword-seed (sentence-transformers/BERTopic extra is not installed)"
    except Exception as exc:
        return keyword_labels, f"keyword-seed (BERTopic did not fit: {type(exc).__name__})"
    return labels, "bertopic-seed"
