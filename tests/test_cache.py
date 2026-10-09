import json
from pathlib import Path

from sermon_insights.captions import fetch_captions
from sermon_insights.catalog import build_catalog, flat_playlist_command
from sermon_insights.songsearch import cached_search, search_command


class _Result:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_commands_are_keyless_yt_dlp():
    playlist = flat_playlist_command("https://www.youtube.com/@example-fellowship/streams")
    search = search_command("uongezeke yesu", 6)
    assert playlist[:3] == ["yt-dlp", "--flat-playlist", "-J"]
    assert search[:4] == ["yt-dlp", "--flat-playlist", "-j", "--no-warnings"]
    assert search[-1].startswith("ytsearch6:")
    blob = " ".join(playlist + search).lower()
    assert "api_key" not in blob
    assert "goog" not in blob


def test_catalog_does_not_refetch(tmp_path: Path):
    calls = []

    def runner(args):
        calls.append(args)
        tab = "streams" if args[-1].endswith("/streams") else "videos"
        payload = {
            "entries": [
                {
                    "id": "FixSermon1a",
                    "title": "WORD || sample",
                    "duration": 2000,
                    "upload_date": "20250615",
                    "live_status": "was_live",
                    "availability": "public",
                }
            ]
            if tab == "streams"
            else []
        }
        return _Result(json.dumps(payload))

    first = build_catalog(
        channel="@example-fellowship",
        since=None,
        raw_dir=tmp_path,
        runner=runner,
        network=True,
    )
    second = build_catalog(
        channel="@example-fellowship",
        since=None,
        raw_dir=tmp_path,
        runner=runner,
        network=True,
    )
    assert len(first) == 1 and first[0]["id"] == "FixSermon1a"
    assert [row["id"] for row in second] == ["FixSermon1a"]
    assert len(calls) == 2  # streams + videos, once


def test_songsearch_cache_is_idempotent(tmp_path: Path):
    path = tmp_path / "songcache.json"
    path.write_text('{"_queries": {}}\n', encoding="utf-8")
    calls = []

    def runner(args):
        calls.append(list(args))
        return _Result(
            '{"id":"abc","title":"Uongezeke","channel":"Artist","view_count":10,"duration":200,"channel_is_verified":true}\n'
        )

    first, cached_first = cached_search("uongezeke", path, runner=runner, sleep_s=0)
    second, cached_second = cached_search("uongezeke", path, runner=runner, sleep_s=0)
    assert cached_first is False and cached_second is True
    assert first["res"][0]["id"] == "abc"
    assert second["res"][0]["title"] == "Uongezeke"
    assert len(calls) == 1


def test_caption_fetch_skips_existing_file(tmp_path: Path):
    calls = []

    class _Api:
        def fetch(self, video_id, languages):
            calls.append(video_id)
            raise AssertionError("should not be called twice")

    transcript = tmp_path / "transcripts"
    transcript.mkdir()
    (transcript / "FixSermon1a.json").write_text('{"segments":[]}\n', encoding="utf-8")
    status = fetch_captions(tmp_path, "FixSermon1a", ["sw", "en"], api=_Api(), network=True, between_videos_s=0)
    assert status == "cached"
    assert calls == []
