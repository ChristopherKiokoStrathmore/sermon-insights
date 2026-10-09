"""YAML config. CLI flags override the file. Paths in the file are relative to the file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _resolve(base: Path, value) -> Path | None:
    if value is None or value == "":
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


@dataclass
class Config:
    channel: str = ""
    since: date | None = None
    languages: list[str] = field(default_factory=lambda: ["sw", "en"])
    cache_dir: Path = field(default_factory=lambda: Path("data").resolve())
    output: Path = field(default_factory=lambda: Path("data/sermon_insights.xlsx").resolve())
    network: bool = True
    offline_fixture: Path | None = None
    drive_dir: Path | None = None
    whisper_model: str | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str | None = None
    whisper_language: str = "sw"
    whisper_cpu_threads: int = 8
    throttle_between_videos: float = 8
    throttle_requests: float = 2
    throttle_subtitles: float = 6
    throttle_ytsearch: float = 4
    retry_waits: list[float] = field(default_factory=lambda: [30, 60, 90])
    detect_bin_s: int = 60
    detect_min_words: int = 25
    detect_gap_bins: int = 3
    detect_max_music: int = 0
    topics_backend: str = "auto"
    topics_min_docs: int = 8
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    summary_backend: str = "auto"
    summary_sentences: int = 3
    worship_manual: Path | None = None
    export_csv: bool = True

    @classmethod
    def from_mapping(cls, data: dict | None, base: Path | None = None) -> Config:
        data = dict(data or {})
        base = (base or Path.cwd()).resolve()
        whisper = data.get("whisper") or {}
        throttle = data.get("throttle") or {}
        detect = data.get("detect") or {}
        topics = data.get("topics") or {}
        summary = data.get("summary") or {}
        cache = _resolve(base, data.get("cache_dir") or "data") or (base / "data")
        output = _resolve(base, data.get("output")) or (cache / "sermon_insights.xlsx")
        return cls(
            channel=str(data.get("channel") or ""),
            since=_as_date(data.get("since")),
            languages=list(data.get("languages") or ["sw", "en"]),
            cache_dir=cache,
            output=output,
            network=bool(data.get("network", True)),
            offline_fixture=_resolve(base, data.get("offline_fixture")),
            drive_dir=_resolve(base, data.get("drive_dir")),
            whisper_model=whisper.get("model"),
            whisper_device=str(whisper.get("device") or "cpu"),
            whisper_compute_type=whisper.get("compute_type"),
            whisper_language=str(whisper.get("language") or "sw"),
            whisper_cpu_threads=int(whisper.get("cpu_threads") or 8),
            throttle_between_videos=float(throttle.get("between_videos_s", 8)),
            throttle_requests=float(throttle.get("request_sleep_s", 2)),
            throttle_subtitles=float(throttle.get("subtitle_sleep_s", 6)),
            throttle_ytsearch=float(throttle.get("ytsearch_sleep_s", 4)),
            retry_waits=[float(item) for item in (throttle.get("retries") or [30, 60, 90])],
            detect_bin_s=int(detect.get("bin_s", 60)),
            detect_min_words=int(detect.get("min_words", 25)),
            detect_gap_bins=int(detect.get("gap_bins", 3)),
            detect_max_music=int(detect.get("max_music_tags", 0)),
            topics_backend=str(topics.get("backend") or "auto"),
            topics_min_docs=int(topics.get("min_docs", 8)),
            embedding_model=str(topics.get("embedding_model") or "paraphrase-multilingual-MiniLM-L12-v2"),
            summary_backend=str(summary.get("backend") or "auto"),
            summary_sentences=int(summary.get("sentences", 3)),
            worship_manual=_resolve(base, data.get("worship_manual")),
            export_csv=bool(data.get("export_csv", True)),
        )


def load_config(path: Path | None, overrides: dict | None = None) -> Config:
    data: dict = {}
    base = Path.cwd()
    if path is not None:
        file = Path(path)
        if file.is_file():
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            base = file.parent
        elif path and str(path) not in ("sermon.yaml", "config/sermon.yaml"):
            raise FileNotFoundError(f"Config file not found: {path}")
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                data[key] = value
    return Config.from_mapping(data, base)
