"""DuckDB tables plus the on-disk cache layout."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import duckdb

from sermon_insights.songsearch import load_cache, save_cache


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("raw", "subs", "transcripts", "worship_transcripts", "audio", "meta"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / "audio" / "worship").mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "sermon.duckdb"
        self.con = duckdb.connect(str(self.db_path))
        self._init()

    def close(self) -> None:
        self.con.close()

    def _init(self) -> None:
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                tab VARCHAR,
                upload_date DATE,
                duration_s INTEGER,
                live_status VARCHAR,
                url VARCHAR,
                kind VARCHAR,
                likely_sermon BOOLEAN,
                availability VARCHAR
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS segments (
                id VARCHAR PRIMARY KEY,
                sermon_start_s INTEGER,
                sermon_end_s INTEGER,
                method VARCHAR,
                confidence VARCHAR,
                source VARCHAR,
                note VARCHAR
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS scripture (
                video_id VARCHAR,
                ref VARCHAR,
                book VARCHAR,
                conf VARCHAR,
                why VARCHAR,
                ts INTEGER,
                link VARCHAR,
                span VARCHAR,
                snippet VARCHAR
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS worship_songs (
                video_id VARCHAR,
                start_s INTEGER,
                end_s INTEGER,
                title VARCHAR,
                artist VARCHAR,
                youtube VARCHAR,
                conf VARCHAR,
                method VARCHAR,
                snippet VARCHAR,
                notes VARCHAR
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS sermon_analysis (
                id VARCHAR PRIMARY KEY,
                preacher VARCHAR,
                summary_en VARCHAR,
                summary_sw VARCHAR,
                theme VARCHAR,
                theme_method VARCHAR,
                message VARCHAR,
                main_passage VARCHAR,
                main_source VARCHAR,
                summary_source VARCHAR
            )
            """
        )

    @property
    def songcache_path(self) -> Path:
        return self.root / "songcache.json"

    def songcache(self) -> dict:
        return load_cache(self.songcache_path)

    def write_songcache(self, data: dict) -> None:
        save_cache(self.songcache_path, data)

    def replace_catalog(self, rows: list[dict]) -> None:
        self.con.execute("DELETE FROM catalog")
        if not rows:
            return
        self.con.executemany(
            """
            INSERT INTO catalog VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["title"],
                    row["tab"],
                    row["upload_date"],
                    row["duration_s"],
                    row["live_status"],
                    row["url"],
                    row["kind"],
                    row["likely_sermon"],
                    row["availability"],
                )
                for row in rows
            ],
        )

    def catalog(self, kind: str | None = None) -> list[dict]:
        sql = "SELECT * FROM catalog"
        if kind:
            sql += " WHERE kind = ?"
            result = self.con.execute(sql + " ORDER BY upload_date, id", [kind])
        else:
            result = self.con.execute(sql + " ORDER BY upload_date, id")
        columns = [item[0] for item in result.description]
        rows = []
        for record in result.fetchall():
            item = dict(zip(columns, record, strict=True))
            if isinstance(item.get("upload_date"), datetime):
                item["upload_date"] = item["upload_date"].date()
            rows.append(item)
        return rows

    def upsert_segment(self, video_id: str, span: dict) -> None:
        self.con.execute("DELETE FROM segments WHERE id = ?", [video_id])
        self.con.execute(
            "INSERT INTO segments VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                video_id,
                span.get("sermon_start_s"),
                span.get("sermon_end_s"),
                span.get("method"),
                span.get("confidence"),
                span.get("source"),
                span.get("note"),
            ],
        )

    def segment(self, video_id: str) -> dict | None:
        result = self.con.execute("SELECT * FROM segments WHERE id = ?", [video_id])
        row = result.fetchone()
        if not row:
            return None
        columns = [item[0] for item in result.description]
        return dict(zip(columns, row, strict=True))

    def replace_scripture(self, video_id: str, refs: list[dict]) -> None:
        self.con.execute("DELETE FROM scripture WHERE video_id = ?", [video_id])
        if not refs:
            return
        self.con.executemany(
            "INSERT INTO scripture VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    video_id,
                    ref["ref"],
                    ref["book"],
                    ref["conf"],
                    ref.get("why") or "",
                    int(ref["ts"]),
                    ref["link"],
                    ref.get("span") or "",
                    ref.get("snippet") or "",
                )
                for ref in refs
            ],
        )

    def scripture_for(self, video_id: str) -> list[dict]:
        result = self.con.execute(
            "SELECT * FROM scripture WHERE video_id = ? ORDER BY ts, ref",
            [video_id],
        )
        columns = [item[0] for item in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

    def replace_songs(self, video_id: str, rows: list[dict]) -> None:
        self.con.execute("DELETE FROM worship_songs WHERE video_id = ?", [video_id])
        if not rows:
            return
        self.con.executemany(
            "INSERT INTO worship_songs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    video_id,
                    int(row["start_s"]),
                    int(row["end_s"]),
                    row["title"],
                    row.get("artist") or "",
                    row.get("youtube") or "",
                    row["confidence"],
                    row.get("method") or "",
                    row.get("snippet") or "",
                    row.get("notes") or "",
                )
                for row in rows
            ],
        )

    def songs(self) -> list[dict]:
        result = self.con.execute(
            """
            SELECT s.*, c.upload_date, c.title AS stream_title, c.url
            FROM worship_songs s
            JOIN catalog c ON c.id = s.video_id
            ORDER BY c.upload_date, s.video_id, s.start_s
            """
        )
        columns = [item[0] for item in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

    def upsert_analysis(self, video_id: str, row: dict) -> None:
        self.con.execute("DELETE FROM sermon_analysis WHERE id = ?", [video_id])
        self.con.execute(
            "INSERT INTO sermon_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                video_id,
                row.get("preacher"),
                row.get("summary_en"),
                row.get("summary_sw"),
                row.get("theme"),
                row.get("theme_method"),
                row.get("message"),
                row.get("main_passage"),
                row.get("main_source"),
                row.get("summary_source"),
            ],
        )

    def analysis(self) -> dict[str, dict]:
        result = self.con.execute("SELECT * FROM sermon_analysis")
        columns = [item[0] for item in result.description]
        rows = {}
        for record in result.fetchall():
            item = dict(zip(columns, record, strict=True))
            rows[item["id"]] = item
        return rows

    def write_json(self, relative: str, payload: dict) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)
