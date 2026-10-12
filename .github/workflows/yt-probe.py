#!/usr/bin/env python3
"""Public-video feasibility probe for a GitHub-hosted runner.

No church channel, no account cookies, no saved media. Each check is recorded
pass/fail with the command and the error text.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path("probe-out")
CHANNEL = "https://www.youtube.com/@ktnnews_kenya"
RUN = os.environ.get("PROBE_RUN", "1")
SUMMARY_PATH = Path(os.environ["GITHUB_STEP_SUMMARY"])
COMMON = ["--js-runtimes", "node", "--retries", "1", "--socket-timeout", "20"]
AUDIO_CLIENTS = ["default", "tv", "web_safari", "mweb", "android_vr", "ios", "web_embedded"]


def redact(text: str) -> str:
    return re.sub(
        r"(?i)(po_?token(?:=|:|\s+))([A-Za-z0-9_\-+/=]{8,})",
        r"\1[redacted]",
        text or "",
    )


def clip(text: str, limit: int = 5000) -> str:
    text = redact(text).strip()
    if not text:
        return "(empty)"
    if len(text) <= limit:
        return text
    return f"… last {limit} chars of {len(text)} …\n" + text[-limit:]


def run_cmd(key: str, args: list[str], timeout: int = 90) -> tuple[int, str, str]:
    folder = ROOT / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cmd.txt").write_text(" ".join(args) + "\n", encoding="utf-8")
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        code, stdout, stderr = completed.returncode, completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        stderr += f"\nTIMEOUT after {timeout}s"
    (folder / "code.txt").write_text(str(code), encoding="utf-8")
    (folder / "stdout.txt").write_text(stdout, encoding="utf-8")
    (folder / "stderr.txt").write_text(stderr, encoding="utf-8")
    return code, stdout, stderr


def versions() -> str:
    lines = []
    for args in (
        ["yt-dlp", "--version"],
        ["node", "--version"],
        ["ffmpeg", "-version"],
    ):
        try:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
            first = (completed.stdout or completed.stderr or "").strip().splitlines()
            lines.append(f"{args[0]}: {first[0] if first else '(no output)'} (exit {completed.returncode})")
        except Exception as exc:
            lines.append(f"{args[0]}: {type(exc).__name__}: {exc}")
    try:
        import importlib.metadata as metadata

        for name in ("yt-dlp", "yt-dlp-ejs", "youtube-transcript-api"):
            try:
                lines.append(f"{name}: {metadata.version(name)}")
            except metadata.PackageNotFoundError:
                lines.append(f"{name}: not installed")
    except Exception as exc:
        lines.append(f"package versions: {type(exc).__name__}: {exc}")
    return "\n".join(lines)


def ipinfo() -> str:
    request = urllib.request.Request("https://ipinfo.io/json", headers={"User-Agent": "sermon-insights-yt-probe"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        return f"ipinfo.io failed: {type(exc).__name__}: {exc}"
    kept = {key: payload.get(key) for key in ("ip", "hostname", "city", "region", "country", "org", "timezone")}
    return json.dumps(kept, indent=2)


def catalog(tab: str) -> tuple[dict, list[str]]:
    url = f"{CHANNEL}/{tab}"
    code, stdout, stderr = run_cmd(
        f"catalog-{tab}",
        ["yt-dlp", "--flat-playlist", "-J", "--playlist-end", "3", *COMMON, url],
        timeout=120,
    )
    ids: list[str] = []
    titles: list[str] = []
    extra = ""
    passed = False
    if code == 0:
        try:
            data = json.loads(stdout)
            entries = data.get("entries") or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("id"):
                    ids.append(str(entry["id"]))
                titles.append(str(entry.get("title") or ""))
            extra = f"Entries: {len(entries)}. Titles: {titles}"
            passed = isinstance(data, dict) and "entries" in data
            if not passed:
                extra = "Exit 0 but stdout has no entries key."
        except Exception as exc:
            extra = f"Exit 0 but stdout was not playlist JSON: {type(exc).__name__}: {exc}"
    command = "yt-dlp --flat-playlist -J --playlist-end 3 " + " ".join(COMMON) + f" {url}"
    return (
        {
            "name": f"catalog /{tab}",
            "passed": passed,
            "code": code,
            "command": command,
            "detail": extra,
            "stdout": "" if passed else stdout,
            "stderr": stderr,
        },
        ids,
    )


def choose_track(tracks: list) -> object | None:
    generated_sw = [
        track
        for track in tracks
        if getattr(track, "is_generated", False) and str(getattr(track, "language_code", "")).lower().startswith("sw")
    ]
    if generated_sw:
        return generated_sw[0]
    generated = [track for track in tracks if getattr(track, "is_generated", False)]
    if generated:
        return generated[0]
    return tracks[0] if tracks else None


def captions_api(video_ids: list[str]) -> tuple[dict, dict, str | None]:
    list_notes: list[str] = []
    fetch_notes: list[str] = []
    chosen: str | None = None
    if not video_ids:
        message = "skipped: catalog /videos returned no video id"
        return (
            {"name": "captions A list", "passed": False, "code": 1, "command": "YouTubeTranscriptApi.list", "detail": message, "stdout": "", "stderr": message},
            {"name": "captions A fetch", "passed": False, "code": 1, "command": "Transcript.fetch", "detail": message, "stdout": "", "stderr": message},
            None,
        )
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        failed = {
            "name": "captions A list",
            "passed": False,
            "code": 1,
            "command": "YouTubeTranscriptApi.list",
            "detail": "",
            "stdout": "",
            "stderr": message,
        }
        failed_fetch = dict(failed)
        failed_fetch["name"] = "captions A fetch"
        failed_fetch["command"] = "Transcript.fetch"
        return failed, failed_fetch, None

    listed_ok = False
    fetched_ok = False
    for video_id in video_ids[:5]:
        try:
            tracks = list(api.list(video_id))
        except Exception as exc:
            list_notes.append(f"{video_id}: {type(exc).__name__}: {exc}")
            continue
        listed_ok = True
        described = ", ".join(
            f"{getattr(track, 'language_code', '?')} generated={getattr(track, 'is_generated', '?')}"
            for track in tracks
        )
        list_notes.append(f"{video_id}: {described or '(no tracks)'}")
        track = choose_track(tracks)
        if track is None:
            fetch_notes.append(f"{video_id}: no track to fetch")
            continue
        try:
            snippets = list(track.fetch())
        except Exception as exc:
            fetch_notes.append(
                f"{video_id} fetch {getattr(track, 'language_code', '?')}: {type(exc).__name__}: {exc}"
            )
            continue
        texts = [str(getattr(snippet, "text", "")).strip() for snippet in snippets]
        texts = [text for text in texts if text]
        sample = texts[0][:80] if texts else ""
        fetch_notes.append(
            f"{video_id}: fetched {getattr(track, 'language_code', '?')} "
            f"generated={getattr(track, 'is_generated', '?')} snippets={len(texts)} first={sample!r}"
        )
        if texts:
            fetched_ok = True
            chosen = video_id
            break
    return (
        {
            "name": "captions A list",
            "passed": listed_ok,
            "code": 0 if listed_ok else 1,
            "command": "YouTubeTranscriptApi().list(video_id)  # up to 5 ids from /videos",
            "detail": "",
            "stdout": "\n".join(list_notes),
            "stderr": "",
        },
        {
            "name": "captions A fetch",
            "passed": fetched_ok,
            "code": 0 if fetched_ok else 1,
            "command": "transcript.fetch()  # generated sw, else generated, else first track",
            "detail": f"video {chosen}" if chosen else "",
            "stdout": "\n".join(fetch_notes),
            "stderr": "",
        },
        chosen,
    )


def captions_ytdlp(video_id: str | None) -> dict:
    if not video_id:
        message = "skipped: no video id"
        return {
            "name": "captions B yt-dlp",
            "passed": False,
            "code": 1,
            "command": "yt-dlp --write-auto-subs --skip-download --sub-langs sw,en",
            "detail": message,
            "stdout": "",
            "stderr": message,
        }
    out = ROOT / "subs"
    out.mkdir(parents=True, exist_ok=True)
    code, stdout, stderr = run_cmd(
        "captions-ytdlp",
        [
            "yt-dlp",
            "--write-auto-subs",
            "--skip-download",
            "--sub-langs",
            "sw,en",
            "--sub-format",
            "json3",
            "--no-playlist",
            *COMMON,
            "-o",
            str(out / "%(id)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        timeout=120,
    )
    files = sorted(path.name for path in out.glob("*") if path.is_file() and path.stat().st_size > 0)
    passed = code == 0 and bool(files)
    detail = f"video {video_id}. Files: {', '.join(files) or '(none)'}"
    if code == 0 and not files:
        detail += ". yt-dlp exited 0 but wrote no subtitle file."
    command = (ROOT / "captions-ytdlp" / "cmd.txt").read_text(encoding="utf-8").strip()
    return {
        "name": "captions B yt-dlp",
        "passed": passed,
        "code": code,
        "command": command,
        "detail": detail,
        "stdout": "" if passed else stdout,
        "stderr": stderr,
    }


def audio_check(name: str, video_id: str | None, client: str | None, verbose: bool = False) -> dict:
    label = f"audio {name}"
    if not video_id:
        message = "skipped: no video id"
        return {
            "name": label,
            "passed": False,
            "code": 1,
            "command": "yt-dlp -f bestaudio --download-sections *0:00-0:05",
            "detail": message,
            "stdout": "",
            "stderr": message,
        }
    out = ROOT / "audio" / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    args = [
        "yt-dlp",
        "-f",
        "bestaudio",
        "--download-sections",
        "*0:00-0:05",
        "--force-keyframes-at-cuts",
        "--no-playlist",
        *COMMON,
        "-o",
        str(out / "%(id)s.%(ext)s"),
    ]
    if client:
        args.extend(["--extractor-args", f"youtube:player_client={client}"])
    if verbose:
        args.append("-v")
    args.append(f"https://www.youtube.com/watch?v={video_id}")
    code, stdout, stderr = run_cmd(f"audio-{name}", args, timeout=100)
    files = [path for path in out.glob("*") if path.is_file() and path.stat().st_size > 0]
    described = ", ".join(f"{path.name} ({path.stat().st_size} bytes)" for path in files) or "(none)"
    for path in files:
        path.unlink()
    passed = code == 0 and bool(files)
    detail = f"video {video_id}. Files: {described}"
    if code == 0 and not files:
        detail += ". yt-dlp exited 0 but wrote no audio."
    command = (ROOT / f"audio-{name}" / "cmd.txt").read_text(encoding="utf-8").strip()
    return {
        "name": label,
        "passed": passed,
        "code": code,
        "command": command,
        "detail": detail,
        "stdout": "" if passed else stdout,
        "stderr": stderr,
    }


def wait_ping(seconds: int = 60) -> str:
    deadline = time.time() + seconds
    last = "no response"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:4416/ping", timeout=3) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2)
    return last


def setup_bgutil() -> dict:
    notes: list[str] = []
    if not shutil.which("docker"):
        notes.append("docker: not on PATH")
        return {
            "name": "bgutil setup",
            "passed": False,
            "code": 1,
            "command": "docker run -d --init -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider",
            "detail": "",
            "stdout": "",
            "stderr": "\n".join(notes),
        }
    subprocess.run(["docker", "rm", "-f", "bgutil-provider"], capture_output=True, text=True, check=False)
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--name",
                "bgutil-provider",
                "-d",
                "--init",
                "-p",
                "127.0.0.1:4416:4416",
                "brainicism/bgutil-ytdlp-pot-provider",
            ],
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        err = exc.stderr or ""
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        notes.append(f"docker run TIMEOUT after 360s\n{err}")
        return {
            "name": "bgutil setup",
            "passed": False,
            "code": 124,
            "command": "docker run -d --init -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider",
            "detail": "",
            "stdout": "",
            "stderr": "\n".join(notes),
        }
    notes.append(f"docker run exit {completed.returncode}")
    notes.append(clip((completed.stdout or "") + "\n" + (completed.stderr or ""), 2000))
    if completed.returncode != 0:
        return {
            "name": "bgutil setup",
            "passed": False,
            "code": completed.returncode,
            "command": "docker run -d --init -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider",
            "detail": "",
            "stdout": completed.stdout or "",
            "stderr": "\n".join(notes),
        }
    ping = wait_ping(90)
    notes.append("ping: " + clip(ping, 1000))
    pip = subprocess.run(
        ["python", "-m", "pip", "install", "bgutil-ytdlp-pot-provider==2.0.2"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    notes.append(f"pip exit {pip.returncode}")
    notes.append(clip((pip.stdout or "") + "\n" + (pip.stderr or ""), 2000))
    logs = subprocess.run(["docker", "logs", "bgutil-provider"], capture_output=True, text=True, timeout=30, check=False)
    notes.append("docker logs:\n" + clip((logs.stdout or "") + "\n" + (logs.stderr or ""), 2000))
    ready = completed.returncode == 0 and pip.returncode == 0 and "version" in ping.lower()
    return {
        "name": "bgutil setup",
        "passed": ready,
        "code": 0 if ready else 1,
        "command": "docker run -d --init -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider && pip install bgutil-ytdlp-pot-provider==2.0.2",
        "detail": "http://127.0.0.1:4416 plugin bgutil-ytdlp-pot-provider==2.0.2",
        "stdout": "",
        "stderr": "\n".join(notes),
    }


def block_signals(blob: str) -> str:
    needles = [
        "Sign in to confirm you're not a bot",
        "confirm you’re not a bot",
        "HTTP Error 403",
        "HTTP Error 429",
        "403: Forbidden",
        "This video is unavailable",
        "LOGIN_REQUIRED",
    ]
    hits = [needle for needle in needles if needle.lower() in blob.lower()]
    if "429" in blob and not any("429" in hit for hit in hits):
        hits.append("429")
    if not hits:
        return "No match for the bot-check phrase, HTTP 403, HTTP 429, LOGIN_REQUIRED, or 'This video is unavailable'."
    return "Matched: " + ", ".join(f"`{hit}`" for hit in hits)


def render(context: str, rows: list[dict]) -> str:
    run_url = (
        f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
        f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    )
    lines = [
        f"# yt-probe run {RUN}",
        "",
        "Public Kenyan news channel only. No church channel. No account cookies.",
        "",
        f"- Actions run: {run_url}",
        f"- Channel: `{CHANNEL}`",
        "",
        "## Context",
        "",
        "```",
        context.strip(),
        "```",
        "",
        "## Results",
        "",
        "| Check | Result | Exit |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        result = "pass" if row["passed"] else "fail"
        lines.append(f"| {row['name']} | {result} | {row['code']} |")
    lines.extend(
        [
            "",
            "## Cookies",
            "",
            "This probe does not use cookies and does not read `YT_COOKIES`.",
            "",
            "A later job could point yt-dlp at a Netscape cookie file kept in a repository secret:",
            "",
            "```bash",
            'if [ -n "$YT_COOKIES" ]; then',
            '  printf \'%s\\n\' "$YT_COOKIES" > "$RUNNER_TEMP/cookies.txt"',
            '  chmod 600 "$RUNNER_TEMP/cookies.txt"',
            '  yt-dlp --cookies "$RUNNER_TEMP/cookies.txt" ...',
            "fi",
            "```",
            "",
            "`YT_COOKIES` would be the cookie-file text, not a path in the repo.",
            "YouTube can ban an account whose cookies are replayed from a datacenter IP,",
            "and a logged-in session used this way conflicts with YouTube's Terms of Service.",
            "A PO token also does not remove an IP login wall; cookies are the extra step,",
            "with that ban and Terms of Service risk. This probe does not take it.",
            "",
        ]
    )
    combined = []
    for row in rows:
        lines.append(f"## {row['name']}: **{'pass' if row['passed'] else 'fail'}**")
        lines.append("")
        lines.append(f"Exit code: `{row['code']}`")
        if row.get("command"):
            lines.append("")
            lines.append("Command:")
            lines.append("")
            lines.append("```")
            lines.append(row["command"])
            lines.append("```")
        if row.get("detail"):
            lines.append("")
            lines.append(row["detail"])
        lines.append("")
        if row.get("stdout", "").strip():
            lines.append("stdout:")
            lines.append("")
            lines.append("```")
            lines.append(clip(row["stdout"]))
            lines.append("```")
            lines.append("")
        lines.append("stderr:")
        lines.append("")
        lines.append("```")
        lines.append(clip(row["stderr"]))
        lines.append("```")
        lines.append("")
        combined.append(row.get("stdout", ""))
        combined.append(row.get("stderr", ""))
    lines.append("## Datacenter block signals")
    lines.append("")
    lines.append(block_signals("\n".join(combined)))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    context = "yt-dlp / node / ffmpeg:\n" + versions() + "\n\nipinfo.io:\n" + ipinfo()
    rows: list[dict] = []
    videos, video_ids = catalog("videos")
    streams, _stream_ids = catalog("streams")
    rows.extend([videos, streams])
    time.sleep(1)
    listed, fetched, chosen = captions_api(video_ids)
    rows.extend([listed, fetched])
    video_id = chosen or (video_ids[0] if video_ids else None)
    time.sleep(1)
    rows.append(captions_ytdlp(video_id))
    for client in AUDIO_CLIENTS:
        time.sleep(1)
        name = client
        rows.append(audio_check(name, video_id, None if client == "default" else client))
    time.sleep(1)
    setup = setup_bgutil()
    rows.append(setup)
    if setup["passed"] and video_id:
        for client in ("default", "mweb"):
            time.sleep(1)
            label = f"bgutil-{client}"
            row = audio_check(label, video_id, None if client == "default" else client, verbose=True)
            row["name"] = f"audio {label}"
            rows.append(row)
    else:
        message = "skipped: no video id" if not video_id else "skipped: bgutil provider was not ready"
        for client in ("default", "mweb"):
            rows.append(
                {
                    "name": f"audio bgutil-{client}",
                    "passed": False,
                    "code": 1,
                    "command": "yt-dlp -f bestaudio (bgutil plugin, not started)",
                    "detail": message,
                    "stdout": "",
                    "stderr": message,
                }
            )
    text = render(context, rows)
    SUMMARY_PATH.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
