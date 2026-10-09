from sermon_insights.transcribe import (
    audio_download_command,
    model_settings,
    opus_transcode_command,
    preload_cuda_libraries,
    preload_shared_objects,
    transcription_options,
)


def test_speech_and_worship_whisper_flags():
    speech = transcription_options("sermon", "sw")
    worship = transcription_options("worship", "sw")
    assert speech["language"] == "sw"
    assert speech["condition_on_previous_text"] is False
    assert speech["vad_filter"] is True
    assert speech["vad_parameters"]["threshold"] == 0.3
    assert speech["vad_parameters"]["min_silence_duration_ms"] == 1000
    assert speech["vad_parameters"]["speech_pad_ms"] == 400
    assert worship["vad_filter"] is False
    assert worship["condition_on_previous_text"] is False
    assert "vad_parameters" not in worship


def test_cuda_defaults_to_medium_float16():
    assert model_settings("cuda", None, None) == ("medium", "float16")
    assert model_settings("cpu", None, None) == ("small", "int8")
    assert model_settings("cuda", "large-v3", "int8_float16") == ("large-v3", "int8_float16")


def test_preload_walks_library_directories(tmp_path):
    first = tmp_path / "cublas"
    second = tmp_path / "cudnn"
    first.mkdir()
    second.mkdir()
    (first / "libcublas.so").write_text("x", encoding="utf-8")
    (second / "libcudnn.so.9").write_text("x", encoding="utf-8")
    loaded = []

    def loader(path):
        loaded.append(path)

    def names_in(directory):
        from pathlib import Path

        return [str(path) for path in sorted(Path(directory).glob("*.so*"))]

    environ = {}
    found = preload_shared_objects([str(first), str(second)], environ, loader, names_in)
    assert found == loaded
    assert len(found) == 2
    assert str(first) in environ["LD_LIBRARY_PATH"]
    assert str(second) in environ["LD_LIBRARY_PATH"]


def test_cuda_preload_is_a_noop_without_the_wheels():
    assert preload_cuda_libraries() == []


def test_audio_commands_do_not_use_an_api_key(tmp_path):
    download = audio_download_command("FixSermon1a", tmp_path)
    assert download[0] == "yt-dlp"
    assert "--no-overwrites" in download
    assert "api" not in " ".join(download).lower()
    transcode = opus_transcode_command(tmp_path / "a.webm", tmp_path / "a.opus")
    assert transcode[0] == "ffmpeg"
    assert "16000" in transcode
    assert "32k" in transcode
