from sermon_insights.detect import detect_span


def _alpha(n: int) -> str:
    """Base-26 token. Digits are split by the speech word regex and collapse uniqueness."""
    chars: list[str] = []
    value = n + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("a") + remainder))
    return "w" + "".join(reversed(chars))


def _line(start: int, text: str, words: int = 28) -> tuple[float, float, str]:
    padding = " ".join(_alpha(start * 40 + i) for i in range(words))
    return (float(start), float(start) + 40, f"{text} {padding}".strip())


def test_short_speech_is_not_a_sermon():
    segments = [_line(i * 60, "neno") for i in range(4)]
    span = detect_span(segments, 4 * 60, source="whisper-sw")
    assert span["confidence"] == "none"
    assert span["sermon_start_s"] is None


def test_long_speech_uses_start_and_end_cues():
    segments = [_line(i * 60, "neno la ibada") for i in range(22)]
    segments[0] = _line(0, "Tufungue biblia tusome")
    segments[20] = _line(20 * 60, "Tuombe sasa")
    span = detect_span(segments, 22 * 60, source="whisper-sw")
    assert span["sermon_start_s"] == 0
    assert span["sermon_end_s"] == 20 * 60
    assert "start-cue" in span["method"]
    assert "end-cue" in span["method"]
    assert span["confidence"] == "high"
    assert span["source"] == "whisper-sw"


def test_music_tags_break_the_speech_run():
    segments = [_line(i * 60, "[music] neno") for i in range(22)]
    span = detect_span(segments, 22 * 60, source="whisper-sw", max_music=0)
    assert span["confidence"] == "none"


def test_small_gaps_stay_inside_one_run():
    segments = [_line(i * 60, "neno") for i in range(12)]
    segments += [_line(i * 60, "neno") for i in range(15, 28)]
    merged = detect_span(segments, 28 * 60, source="yt-sw-orig", gap_bins=3)
    split = detect_span(segments, 28 * 60, source="yt-sw-orig", gap_bins=0)
    assert merged["sermon_start_s"] == 0
    assert merged["sermon_end_s"] is not None
    assert split["sermon_start_s"] is not None
    assert (merged["sermon_end_s"] - merged["sermon_start_s"]) > (
        split["sermon_end_s"] - split["sermon_start_s"]
    )
