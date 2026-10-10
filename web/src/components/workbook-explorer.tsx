"use client";

import { useMemo, useState } from "react";
import { BarList } from "@/components/bar-list";
import {
  isNoteRow,
  refsPerMonth,
  rowMatches,
  rowNeedsVerify,
  topBooks,
  topSongs,
  type ParsedWorkbook,
  type SheetRow,
} from "@/lib/workbook";

type TabId = "sermons" | "scripture" | "worship" | "songs" | "topics";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "high", label: "High" },
  { id: "medium", label: "Medium" },
  { id: "low", label: "Low" },
  { id: "verify", label: "(verify)" },
] as const;

function confidenceOf(row: SheetRow): string {
  return (row.Confidence || row["Detection confidence"] || "").toLowerCase();
}

function matchesFilter(row: SheetRow, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "verify") return rowNeedsVerify(row);
  return confidenceOf(row) === filter;
}

function RichText({ value }: { value: string }) {
  const parts = value.split(/(https?:\/\/[^\s]+)/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("http") ? (
          <a key={index} href={part} target="_blank" rel="noreferrer">
            {part}
          </a>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

function CellValue({ value }: { value: string }) {
  if (!value) return <span className="muted">—</span>;
  if (value.length > 220 && !value.startsWith("http")) {
    return (
      <details>
        <summary>{value.slice(0, 160)}…</summary>
        <RichText value={value} />
      </details>
    );
  }
  return <RichText value={value} />;
}

export function WorkbookExplorer({
  workbook,
  source,
}: {
  workbook: ParsedWorkbook;
  source: "sample" | "local";
}) {
  const [tab, setTab] = useState<TabId>("sermons");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");

  const tabs = useMemo(
    () =>
      [
        { id: "sermons" as const, label: "Sermons", rows: workbook.sermons },
        { id: "scripture" as const, label: "Scripture", rows: workbook.scripture },
        { id: "worship" as const, label: "Worship Songs", rows: workbook.worshipSongs },
        {
          id: "songs" as const,
          label: "Song List",
          rows: workbook.songList.filter((row) => !isNoteRow(row)),
        },
        { id: "topics" as const, label: "Topics & Verses", rows: workbook.topics },
      ] satisfies { id: TabId; label: string; rows: SheetRow[] }[],
    [workbook],
  );

  const active = tabs.find((item) => item.id === tab) ?? tabs[0];
  const visible = active.rows.filter((row) => rowMatches(row, query) && matchesFilter(row, filter));
  const columns = active.rows[0] ? Object.keys(active.rows[0]) : [];
  const note = workbook.songList.find(isNoteRow);
  const noteText = note ? Object.values(note).find((value) => value.startsWith("Excluded:")) : "";
  const books = topBooks(workbook.scripture);
  const months = refsPerMonth(workbook.scripture);
  const songs = topSongs(workbook.songList);

  return (
    <div className="explorer">
      {source === "sample" ? (
        <aside className="banner">
          <strong>Sample data.</strong> One synthetic sermon and one synthetic worship set, generated
          from the offline fixture. Not a real channel, and not a count of anyone&apos;s ministry.
        </aside>
      ) : (
        <aside className="banner">
          <strong>This file stayed in the browser.</strong>
          {workbook.fileName ? ` Opened ${workbook.fileName}.` : ""} Nothing was uploaded.
        </aside>
      )}

      {workbook.missing.length > 0 ? (
        <p className="banner warn">
          Missing {workbook.missing.join(", ")}. Sheets in the file:{" "}
          {workbook.sheetNames.join(", ") || "none"}.
        </p>
      ) : null}

      <section className="charts" aria-label="Counts from this workbook">
        <BarList
          title="Books cited"
          note="Rows on the Scripture sheet, grouped by the Book column."
          items={books}
          empty="No Book values in this file."
        />
        <BarList
          title="References by month"
          note="Scripture rows whose stream date starts with a year and month."
          items={months}
          empty="No dated scripture rows in this file."
        />
        <BarList
          title="Songs that cleared the list"
          note="Song List titles and the times-sung column. Low and unidentified rows stay off this chart."
          items={songs}
          empty="No Song List titles in this file."
        />
      </section>

      <div className="toolbar">
        <div className="tabs" role="tablist" aria-label="Workbook sheets">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`tab-${item.id}`}
              aria-selected={item.id === active.id}
              aria-controls={`panel-${item.id}`}
              className={item.id === active.id ? "tab active" : "tab"}
              onClick={() => {
                setTab(item.id);
                setQuery("");
                setFilter("all");
              }}
            >
              {item.label}
              <span className="tab-count">{item.rows.length}</span>
            </button>
          ))}
        </div>
        <div className="filters">
          <label className="search">
            <span className="search-label">Search this sheet</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Verse, title, phrase"
              type="search"
            />
          </label>
          <div className="filter-row" role="group" aria-label="Confidence filter">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={filter === item.id ? "chip active" : "chip"}
                aria-pressed={filter === item.id}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <p className="result-count">
        {visible.length} of {active.rows.length} rows
        {query.trim() ? ` matching “${query.trim()}”` : ""}
        {filter !== "all" ? ` · ${filter}` : ""}
      </p>

      <div
        role="tabpanel"
        id={`panel-${active.id}`}
        aria-labelledby={`tab-${active.id}`}
        className="table-wrap"
      >
        {visible.length === 0 ? (
          <p className="empty">Nothing on this sheet matches.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Flag</th>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row, index) => {
                const verify = rowNeedsVerify(row);
                return (
                  <tr key={index} className={verify ? "verify-row" : undefined}>
                    <td data-label="Flag">
                      {verify ? <span className="flag-pill">verify</span> : <span className="muted">—</span>}
                    </td>
                    {columns.map((column) => (
                      <td key={column} data-label={column}>
                        <CellValue value={row[column] ?? ""} />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {active.id === "songs" && noteText ? <p className="sheet-note">{noteText}</p> : null}
    </div>
  );
}
