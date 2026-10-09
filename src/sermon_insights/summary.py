"""Extractive sermon summaries.

The lines in the summary are copied from the transcript. Nothing is
paraphrased and nothing is translated. When sentence-transformers is
installed and the caller asks for embeddings, sentences are ranked by
cosine similarity to the centroid. Otherwise they are ranked by overlap
with the other sentences (lexical centrality). The column that used to
hold a hand-written English summary now carries these verbatim lines plus
an explicit method label.
"""

from __future__ import annotations

import re
from collections import Counter

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z']{3,}")
PREACHER = re.compile(
    r"\b(?:Pastor|Pasta|Bishop|Askofu|Apostle|Mtume|Evangelist|Mwinjilisti|Reverend|Rev)\.?\s+"
    r"([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)"
)
NOT_A_NAME = set(
    "Yesu Jesus Mungu God Bwana Lord Paulo Paul Petro Peter Elisha Elija Daudi David "
    "Musa Moses Hakuna Huyo Yule Huyu Amen Haleluya The And Kwa Hii Akasema Anasema".split()
)
_ENGLISH_HINTS = {
    "the",
    "and",
    "of",
    "to",
    "a",
    "in",
    "is",
    "that",
    "for",
    "with",
    "love",
    "this",
    "from",
    "was",
    "are",
}


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE.split(text.replace("\n", " ").strip())
    return [part.strip() for part in parts if len(part.split()) >= 4]


def _tokens(sentence: str) -> set[str]:
    return set(_WORD.findall(sentence.lower()))


def lexical_scores(sentences: list[str]) -> list[float]:
    docs = [_tokens(sentence) for sentence in sentences]
    scores = []
    for index, tokens in enumerate(docs):
        if not tokens:
            scores.append(0.0)
            continue
        overlap = 0.0
        for other_index, other in enumerate(docs):
            if other_index == index or not other:
                continue
            overlap += len(tokens & other) / len(tokens | other)
        scores.append(overlap)
    return scores


def embedding_scores(sentences: list[str], encode) -> list[float]:
    import numpy as np

    vectors = np.asarray(encode(sentences), dtype=float)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    centroid = vectors.mean(axis=0)
    norms = np.linalg.norm(vectors, axis=1) * (np.linalg.norm(centroid) or 1.0)
    sims = vectors @ centroid / np.clip(norms, 1e-9, None)
    return [float(value) for value in sims]


def _pick(sentences: list[str], scores: list[float], k: int) -> list[str]:
    order = sorted(range(len(sentences)), key=lambda index: (-scores[index], index))
    chosen: list[str] = []
    chosen_tokens: list[set[str]] = []
    for index in order:
        tokens = _tokens(sentences[index])
        if any(tokens and prev and len(tokens & prev) / len(tokens | prev) > 0.6 for prev in chosen_tokens):
            continue
        chosen.append(sentences[index])
        chosen_tokens.append(tokens)
        if len(chosen) >= k:
            break
    return chosen


def _mostly_english(text: str) -> bool:
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) < 4:
        return False
    return sum(word in _ENGLISH_HINTS for word in words) / len(words) >= 0.2


def preacher_name(text: str) -> str:
    names = Counter(
        match for match in PREACHER.findall(text) if match.split()[0] not in NOT_A_NAME
    )
    if not names:
        return "Not detected"
    return names.most_common(1)[0][0] + " (verify)"


def extractive_summary(
    segments: list[tuple[float, float, str]],
    start_s: float,
    end_s: float,
    *,
    sentences: int = 3,
    backend: str = "auto",
    encode=None,
) -> dict:
    """Return verbatim opening text and a few central sentences.

    ``backend`` is ``lexical``, ``embedding``, or ``auto``. ``auto`` uses
    ``encode`` when the caller passes one, and lexical centrality otherwise.
    This function does not download a model.
    """
    window = [segment for segment in segments if start_s <= segment[0] <= end_s]
    body = " ".join(segment[2] for segment in window)
    opening = re.sub(r"\s+", " ", body).strip()[:300]
    sentence_list = split_sentences(body)
    method = "extractive-lexical"
    if not sentence_list:
        return {
            "en": "No transcript sentences long enough to extract.",
            "sw": opening,
            "message": "",
            "source": method,
            "preacher": preacher_name(body),
        }
    use_embedding = encode is not None and backend in ("auto", "embedding")
    if use_embedding:
        scores = embedding_scores(sentence_list, encode)
        method = "extractive-embedding"
    else:
        scores = lexical_scores(sentence_list)
        method = "extractive-lexical"
    picked = _pick(sentence_list, scores, sentences)
    verbatim = " ".join(picked)
    if _mostly_english(verbatim):
        english = verbatim
    else:
        english = "Verbatim extract (original language, not a translation): " + verbatim
    return {
        "en": english,
        "sw": opening,
        "message": picked[0][:180],
        "source": method,
        "preacher": preacher_name(body),
    }


def try_sentence_encoder(model_name: str):
    """Return ``encode(list[str]) -> vectors`` when sentence-transformers imports.

    Import failure returns ``None``. The model download, if any, happens only
    when the caller has asked for the embedding backend.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    model = SentenceTransformer(model_name)
    return model.encode
