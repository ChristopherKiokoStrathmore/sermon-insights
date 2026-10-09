"""Command line. ``sermon run`` walks every stage; each stage can also be resumed alone."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sermon_insights import __version__
from sermon_insights.config import load_config
from sermon_insights.pipeline import STAGES, run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sermon",
        description=(
            "Turn a church YouTube channel's public livestreams into sermon spans, "
            "Kiswahili-first scripture references, extractive summaries, themes, "
            "and worship-song notes. No YouTube Data API key."
        ),
    )
    parser.add_argument("--version", action="version", version=f"sermon-insights {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_shared(command: argparse.ArgumentParser, *, with_channel: bool) -> None:
        command.add_argument("--config", type=Path, help="YAML config. Paths inside it are relative to the file.")
        if with_channel:
            command.add_argument("--channel", help="Channel handle, for example @example-fellowship")
            command.add_argument("--since", help="Include uploads on or after this date (YYYY-MM-DD)")
        command.add_argument(
            "--offline",
            action="store_true",
            help="Do not call yt-dlp or the transcript API. Read the offline fixture and cache only.",
        )
        command.add_argument(
            "--force",
            action="store_true",
            help="Forget negative caption markers and recompute. Already downloaded files stay put.",
        )

    run = sub.add_parser("run", help="Run every stage: catalog through workbook")
    add_shared(run, with_channel=True)
    for stage in STAGES:
        command = sub.add_parser(stage, help=f"Run only the {stage} stage (resumable)")
        add_shared(command, with_channel=True)
    return parser


def _build_config(args: argparse.Namespace):
    path = args.config
    if path is None and Path("sermon.yaml").is_file():
        path = Path("sermon.yaml")
    if args.config is not None and not Path(args.config).is_file():
        raise SystemExit(f"Config file not found: {args.config}")
    overrides = {}
    if getattr(args, "channel", None):
        overrides["channel"] = args.channel
    if getattr(args, "since", None):
        overrides["since"] = args.since
    if getattr(args, "offline", False):
        overrides["network"] = False
    return load_config(path if path and Path(path).is_file() else None, overrides)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    cfg = _build_config(args)
    stages = None if args.command == "run" else [args.command]
    report = run_pipeline(cfg, stages, force=bool(args.force))
    print(json.dumps(report, indent=2))
    return 0
