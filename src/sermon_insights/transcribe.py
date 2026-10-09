"""faster-whisper settings that survived real Kiswahili livestreams.

Speech uses a light VAD. Singing does not: the VAD treats melody as silence
and drops the lyric. ``condition_on_previous_text`` stays off in both cases
so a repeated chorus does not lock the decoder into a loop.

On a Colab T4 the working setup is ``medium`` / ``float16`` / ``cuda`` /
``language=sw``. CPU fallback is ``small`` / ``int8``. YouTube blocks Colab
IP ranges, so audio is fetched on your machine and only then read from a
Drive folder. This module never asks Colab to call yt-dlp.
"""

from __future__ import annotations

import os
from pathlib import Path


def model_settings(device: str, model: str | None, compute_type: str | None) -> tuple[str, str]:
    if device == "cuda":
        return (model or "medium", compute_type or "float16")
    return (model or "small", compute_type or "int8")


def transcription_options(kind: str, language: str = "sw") -> dict:
    """Whisper flags for ``sermon`` speech or ``worship`` singing."""
    options = {
        "language": language,
        "beam_size": 1,
        "condition_on_previous_text": False,
    }
    if kind == "worship":
        options["vad_filter"] = False
        return options
    options["vad_filter"] = True
    options["vad_parameters"] = {
        "threshold": 0.3,
        "min_silence_duration_ms": 1000,
        "speech_pad_ms": 400,
    }
    return options


def preload_shared_objects(directories: list[str], environ: dict, loader, names_in) -> list[str]:
    """``ctypes.CDLL`` every ``*.so*`` under ``directories`` and prepend them to ``LD_LIBRARY_PATH``."""
    current = environ.get("LD_LIBRARY_PATH", "")
    environ["LD_LIBRARY_PATH"] = ":".join([*directories, current] if current else directories)
    loaded = []
    for directory in directories:
        for filename in names_in(directory):
            try:
                loader(filename)
            except OSError:
                continue
            loaded.append(filename)
    return loaded


def preload_cuda_libraries() -> list[str]:
    """Load the cuBLAS/cuDNN wheels before ``WhisperModel(..., device='cuda')``.

    Colab's loader does not see ``nvidia-cublas-cu12`` / ``nvidia-cudnn-cu12``
    unless those ``.so`` files are opened with ctypes and placed on
    ``LD_LIBRARY_PATH``. Returns ``[]`` when the wheels are not installed.
    """
    try:
        import nvidia.cublas.lib as cublas
        import nvidia.cudnn.lib as cudnn
    except ImportError:
        return []
    import ctypes
    import glob

    directories = [
        os.path.dirname(cublas.__file__),
        os.path.dirname(cudnn.__file__),
    ]

    def names_in(directory: str) -> list[str]:
        return sorted(glob.glob(os.path.join(directory, "*.so*")))

    return preload_shared_objects(directories, os.environ, ctypes.CDLL, names_in)


def audio_download_command(video_id: str, directory: Path, sleep_requests: float = 2) -> list[str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    return [
        "yt-dlp",
        "-f",
        "bestaudio",
        "--no-overwrites",
        "--sleep-requests",
        str(sleep_requests),
        "-o",
        str(directory / f"{video_id}.%(ext)s"),
        url,
    ]


def opus_transcode_command(source: Path, dest: Path) -> list[str]:
    """16 kHz mono Opus at 32 kbps: small enough to hand to Colab via Drive."""
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        str(dest),
    ]


def existing_audio(directory: Path, video_id: str) -> Path | None:
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob(f"{video_id}.*")):
        if path.suffix == ".part" or not path.is_file() or path.stat().st_size == 0:
            continue
        return path
    return None


def transcribe_file(
    audio_path: Path,
    *,
    kind: str,
    device: str = "cpu",
    model: str | None = None,
    compute_type: str | None = None,
    language: str = "sw",
    cpu_threads: int = 8,
) -> dict:
    """Transcribe one audio file. Imports faster-whisper only when called."""
    if device == "cuda":
        preload_cuda_libraries()
    from faster_whisper import WhisperModel

    model_name, ctype = model_settings(device, model, compute_type)
    threads = cpu_threads if device == "cpu" else 0
    whisper = WhisperModel(model_name, device=device, compute_type=ctype, cpu_threads=threads)
    options = transcription_options(kind, language)
    segments, info = whisper.transcribe(str(audio_path), **options)
    rows = [
        {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
        for segment in segments
        if segment.text and segment.text.strip()
    ]
    return {
        "language": getattr(info, "language", language),
        "lang_prob": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "model": model_name,
        "device": device,
        "compute_type": ctype,
        "segments": rows,
    }
