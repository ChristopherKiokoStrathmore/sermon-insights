"use client";

import { useState } from "react";
import { WorkbookExplorer } from "@/components/workbook-explorer";
import { parseWorkbookArrayBuffer, type ParsedWorkbook } from "@/lib/workbook";

export function OpenWorkbook() {
  const [workbook, setWorkbook] = useState<ParsedWorkbook | null>(null);
  const [error, setError] = useState("");
  const [reading, setReading] = useState(false);

  async function readFile(file: File | undefined) {
    if (!file) return;
    setError("");
    setReading(true);
    try {
      const data = await file.arrayBuffer();
      const parsed = await parseWorkbookArrayBuffer(data);
      parsed.fileName = file.name;
      if (parsed.sheetNames.length === 0) {
        setWorkbook(null);
        setError("This file has no sheets.");
        return;
      }
      setWorkbook(parsed);
    } catch {
      setWorkbook(null);
      setError("Could not read that file as an Excel workbook. sermon-insights writes a .xlsx.");
    } finally {
      setReading(false);
    }
  }

  return (
    <div>
      <label
        className="drop"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void readFile(event.dataTransfer.files[0]);
        }}
      >
        <input
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => void readFile(event.target.files?.[0])}
        />
        <span className="drop-title">{reading ? "Reading…" : "Drop sermon_insights.xlsx"}</span>
        <span className="drop-copy">
          SheetJS parses it here. The file is not sent to a server, and this site has no upload
          endpoint.
        </span>
      </label>
      {error ? (
        <p className="banner warn" role="alert">
          {error}
        </p>
      ) : null}
      {workbook ? <WorkbookExplorer workbook={workbook} source="local" /> : null}
    </div>
  );
}
