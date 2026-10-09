"""Resumable stages. Downloads are skipped when the file is already on disk."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from sermon_insights import songs as songmod
from sermon_insights.captions import already_captioned, fetch_captions
from sermon_insights.catalog import build_catalog
from sermon_insights.config import Config
from sermon_insights.detect import detect_span
from sermon_insights.export import write_workbook
from sermon_insights.scripture import extract_timed, get_index, guess_main_passage
from sermon_insights.segments import load_segments, write_transcript
from sermon_insights.store import Store
from sermon_insights.summary import extractive_summary, try_sentence_encoder
from sermon_insights.topics import assign_themes
from sermon_insights.transcribe import (
    audio_download_command,
    existing_audio,
    opus_transcode_command,
    transcribe_file,
)

STAGES = [
    "catalog",
    "captions",
    "transcribe",
    "detect",
    "scripture",
    "songs",
    "topics",
    "export",
]


def seed_offline(cfg: Config, store: Store) -> None:
    fixture = cfg.offline_fixture
    if fixture is None or not fixture.is_dir():
        return
    for name in ("raw", "transcripts", "worship_transcripts", "subs", "audio"):
        source = fixture / name
        if not source.is_dir():
            continue
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            target = store.root / name / path.relative_to(source)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    bundled_cache = fixture / "songcache.json"
    if bundled_cache.is_file() and not store.songcache_path.exists():
        shutil.copy2(bundled_cache, store.songcache_path)


def ensure_songcache(store: Store) -> None:
    if store.songcache_path.exists():
        return
    seed = Path(__file__).resolve().parent / "data" / "songcache.seed.json"
    if seed.is_file():
        shutil.copy2(seed, store.songcache_path)
        return
    store.write_songcache({"_queries": {}})


def _clear_negative_cache(store: Store) -> None:
    for path in (store.root / "subs").glob("*.none"):
        path.unlink()


def stage_catalog(cfg: Config, store: Store, runner=None) -> dict:
    if cfg.network and not cfg.channel:
        raise RuntimeError("A channel handle is required, for example --channel @example")
    rows = build_catalog(
        channel=cfg.channel or "@offline",
        since=cfg.since,
        raw_dir=store.root / "raw",
        runner=runner,
        network=cfg.network,
    )
    store.replace_catalog(rows)
    return {"videos": len(rows), "sermons": sum(row["kind"] == "sermon" for row in rows), "worship": sum(row["kind"] == "worship" for row in rows)}


def stage_captions(cfg: Config, store: Store, runner=None, api=None, sleeper=None) -> dict:
    counts = {"cached": 0, "fetched": 0, "none": 0, "skipped": 0, "failed": 0}
    for video in store.catalog():
        if already_captioned(store.root, video["id"]):
            counts["cached"] += 1
            continue
        status = fetch_captions(
            store.root,
            video["id"],
            cfg.languages,
            api=api,
            runner=runner,
            network=cfg.network,
            sleep_requests=cfg.throttle_requests,
            sleep_subtitles=cfg.throttle_subtitles,
            sleeper=sleeper,
            between_videos_s=cfg.throttle_between_videos,
        )
        if status == "cached":
            counts["cached"] += 1
        elif status in ("skipped-offline",):
            counts["skipped"] += 1
        elif status == "none":
            counts["none"] += 1
        elif status == "failed":
            counts["failed"] += 1
        else:
            counts["fetched"] += 1
    return counts


def _audio_dir(store: Store, kind: str) -> Path:
    return store.root / "audio" / "worship" if kind == "worship" else store.root / "audio"


def stage_transcribe(cfg: Config, store: Store, runner=None) -> dict:
    """Whisper only where captions are missing. Existing audio is not downloaded again."""
    from sermon_insights.catalog import default_runner

    runner = runner or default_runner
    done = skipped = 0
    for video in store.catalog():
        kind = "worship" if video["kind"] == "worship" else "sermon"
        if kind == "worship" and (store.root / "worship_transcripts" / f"{video['id']}.json").is_file():
            skipped += 1
            continue
        sw = store.root / "subs" / f"{video['id']}.sw-orig.json3"
        en = store.root / "subs" / f"{video['id']}.en-orig.json3"
        transcript = store.root / "transcripts" / f"{video['id']}.json"
        if sw.is_file() or en.is_file() or transcript.is_file():
            skipped += 1
            continue
        directory = _audio_dir(store, kind)
        audio = existing_audio(directory, video["id"])
        if audio is None and cfg.network:
            runner(audio_download_command(video["id"], directory, cfg.throttle_requests))
            audio = existing_audio(directory, video["id"])
        if audio is None:
            continue
        if cfg.drive_dir is not None:
            dest = cfg.drive_dir / ("worship" if kind == "worship" else "sermons")
            dest.mkdir(parents=True, exist_ok=True)
            opus = dest / f"{video['id']}.opus"
            if not opus.exists():
                runner(opus_transcode_command(audio, opus))
        payload = transcribe_file(
            audio,
            kind=kind,
            device=cfg.whisper_device,
            model=cfg.whisper_model,
            compute_type=cfg.whisper_compute_type,
            language=cfg.whisper_language,
            cpu_threads=cfg.whisper_cpu_threads,
        )
        payload["source"] = f"whisper-{payload.get('language') or cfg.whisper_language}"
        target_dir = "worship_transcripts" if kind == "worship" else "transcripts"
        write_transcript(
            store.root / target_dir / f"{video['id']}.json",
            video["id"],
            [(row["start"], row["end"], row["text"]) for row in payload["segments"]],
            language=payload.get("language") or cfg.whisper_language,
            source=payload["source"],
            extra={"model": payload.get("model"), "duration": payload.get("duration")},
        )
        done += 1
    return {"transcribed": done, "skipped": skipped}


def stage_detect(cfg: Config, store: Store) -> dict:
    kept = 0
    for video in store.catalog("sermon"):
        segments, source, _meta = load_segments(store.root, video["id"])
        duration = video.get("duration_s") or (segments[-1][1] if segments else 0)
        span = detect_span(
            segments,
            float(duration or 0),
            source=source or "none",
            min_words=cfg.detect_min_words,
            gap_bins=cfg.detect_gap_bins,
            max_music=cfg.detect_max_music,
            bin_s=cfg.detect_bin_s,
        )
        store.upsert_segment(video["id"], span)
        if span.get("sermon_start_s") is not None:
            kept += 1
    return {"sermons_with_span": kept}


def stage_scripture(cfg: Config, store: Store) -> dict:
    index = get_index(cfg.languages)
    total = 0
    for video in store.catalog("sermon"):
        segments, _source, _meta = load_segments(store.root, video["id"])
        span = store.segment(video["id"]) or {}
        start = span.get("sermon_start_s")
        end = span.get("sermon_end_s")
        if start is None:
            start, end = 0, video.get("duration_s") or 0
        refs = extract_timed(video["id"], segments, float(start), float(end or start), index)
        store.replace_scripture(video["id"], refs)
        total += len(refs)
    return {"references": total}


def _source_label(source: str | None, meta: dict) -> str:
    if source and str(source).startswith("yt-"):
        return f"Captions ({source})"
    model = meta.get("model") or "medium"
    language = meta.get("language") or "sw"
    return f"Whisper transcript ({model}, {language})"


def stage_songs(cfg: Config, store: Store) -> dict:
    manual = {}
    if cfg.worship_manual and cfg.worship_manual.is_file():
        manual = json.loads(cfg.worship_manual.read_text(encoding="utf-8"))
    cache = store.songcache()
    blocks = 0
    for video in store.catalog("worship"):
        segments, source, meta = load_segments(store.root, video["id"], worship=True)
        duration = float(video.get("duration_s") or meta.get("duration") or 0)
        if not segments:
            store.replace_songs(
                video["id"],
                [
                    {
                        "start_s": 0,
                        "end_s": int(duration),
                        "title": "Unidentified",
                        "artist": "",
                        "youtube": "",
                        "confidence": "low",
                        "method": "no transcript",
                        "snippet": "",
                        "notes": "No lyrics transcribed yet.",
                    }
                ],
            )
            blocks += 1
            continue
        rows = songmod.segment_worship(
            segments,
            duration,
            cache,
            manual=manual.get(video["id"]) or [],
            source_label=_source_label(source, meta),
        )
        store.replace_songs(video["id"], rows)
        blocks += len(rows)
    return {"song_segments": blocks}


def _sermon_document(store: Store, video_id: str) -> str:
    segments, _source, _meta = load_segments(store.root, video_id)
    span = store.segment(video_id) or {}
    start = span.get("sermon_start_s")
    end = span.get("sermon_end_s")
    if start is None:
        text = " ".join(segment[2] for segment in segments)
    else:
        text = " ".join(segment[2] for segment in segments if start <= segment[0] <= end)
    refs = store.scripture_for(video_id)
    quoted = " ".join(f"{ref['ref']} {ref.get('snippet') or ''}" for ref in refs)
    return (text + "\n" + quoted).strip()


def stage_topics(cfg: Config, store: Store) -> dict:
    index = get_index(cfg.languages)
    videos = [video for video in store.catalog("sermon") if load_segments(store.root, video["id"])[1]]
    documents = [_sermon_document(store, video["id"]) for video in videos]
    labels, method = assign_themes(
        documents,
        backend=cfg.topics_backend,
        min_docs=cfg.topics_min_docs,
        model_name=cfg.embedding_model,
    )
    encode = None
    if cfg.summary_backend == "embedding":
        encode = try_sentence_encoder(cfg.embedding_model)
    for video, label in zip(videos, labels, strict=True):
        segments, _source, _meta = load_segments(store.root, video["id"])
        span = store.segment(video["id"]) or {}
        start = span.get("sermon_start_s")
        end = span.get("sermon_end_s")
        if start is None:
            start, end = 0, video.get("duration_s") or 0
        refs = store.scripture_for(video["id"])
        summary = extractive_summary(
            segments,
            float(start),
            float(end or start),
            sentences=cfg.summary_sentences,
            backend=cfg.summary_backend,
            encode=encode,
        )
        main = guess_main_passage(segments, float(start), float(end or start), refs, index)
        store.upsert_analysis(
            video["id"],
            {
                "preacher": summary["preacher"],
                "summary_en": summary["en"],
                "summary_sw": summary["sw"],
                "theme": label,
                "theme_method": method,
                "message": summary["message"],
                "main_passage": main,
                "main_source": "main text (auto, verify)" if main else "",
                "summary_source": summary["source"],
            },
        )
    return {"sermons": len(videos), "theme_method": method}


def stage_export(cfg: Config, store: Store) -> dict:
    path = write_workbook(
        store,
        cfg.output,
        languages=cfg.languages,
        export_csv=cfg.export_csv,
    )
    return {"workbook": str(path)}


_STAGE_FUNCS = {
    "catalog": stage_catalog,
    "captions": stage_captions,
    "transcribe": stage_transcribe,
    "detect": stage_detect,
    "scripture": stage_scripture,
    "songs": stage_songs,
    "topics": stage_topics,
    "export": stage_export,
}


def run_pipeline(
    cfg: Config,
    stages: list[str] | None = None,
    *,
    runner=None,
    sleeper=None,
    api=None,
    force: bool = False,
) -> dict:
    store = Store(cfg.cache_dir)
    try:
        seed_offline(cfg, store)
        ensure_songcache(store)
        if force:
            _clear_negative_cache(store)
        selected = stages or STAGES
        unknown = [name for name in selected if name not in _STAGE_FUNCS]
        if unknown:
            raise ValueError(f"Unknown stage(s): {', '.join(unknown)}")
        report = {}
        for name in selected:
            func = _STAGE_FUNCS[name]
            if name == "captions":
                report[name] = func(cfg, store, runner=runner, api=api, sleeper=sleeper)
            elif name in ("catalog", "transcribe"):
                report[name] = func(cfg, store, runner=runner)
            else:
                report[name] = func(cfg, store)
        return report
    finally:
        store.close()
