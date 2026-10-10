export type SheetRow = Record<string, string>;

export type ParsedWorkbook = {
  fileName?: string;
  sheetNames: string[];
  missing: string[];
  sermons: SheetRow[];
  scripture: SheetRow[];
  worshipSongs: SheetRow[];
  songList: SheetRow[];
  topics: SheetRow[];
};

export type CountItem = { label: string; count: number };

export const SHEET_NAMES = {
  sermons: "Sermons",
  scripture: "Scripture",
  worshipSongs: "Worship Songs",
  songList: "Song List",
  topics: "Topics & Verses",
} as const;

type XlsxModule = typeof import("xlsx");

function cellToString(XLSX: XlsxModule, cell: import("xlsx").CellObject | undefined): string {
  if (!cell || cell.v == null || cell.v === "") return "";
  if (cell.t === "n" && typeof cell.v === "number" && cell.z && XLSX.SSF.is_date(cell.z)) {
    const parsed = XLSX.SSF.parse_date_code(cell.v);
    if (parsed) {
      const pad = (value: number) => String(value).padStart(2, "0");
      return `${parsed.y}-${pad(parsed.m)}-${pad(parsed.d)}`;
    }
  }
  if (typeof cell.v === "number") {
    return Number.isInteger(cell.v) ? String(cell.v) : String(cell.v);
  }
  if (cell.v instanceof Date) {
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${cell.v.getFullYear()}-${pad(cell.v.getMonth() + 1)}-${pad(cell.v.getDate())}`;
  }
  return String(cell.w ?? cell.v).replace(/\r\n/g, "\n").trim();
}

export function rowsFromSheet(XLSX: XlsxModule, sheet: import("xlsx").WorkSheet | undefined): SheetRow[] {
  if (!sheet || !sheet["!ref"]) return [];
  const range = XLSX.utils.decode_range(sheet["!ref"]);
  const headers: string[] = [];
  for (let column = range.s.c; column <= range.e.c; column += 1) {
    const cell = sheet[XLSX.utils.encode_cell({ r: range.s.r, c: column })] as
      | import("xlsx").CellObject
      | undefined;
    headers.push(cellToString(XLSX, cell));
  }
  const rows: SheetRow[] = [];
  for (let rowIndex = range.s.r + 1; rowIndex <= range.e.r; rowIndex += 1) {
    const record: SheetRow = {};
    let any = false;
    headers.forEach((header, offset) => {
      if (!header) return;
      const cell = sheet[XLSX.utils.encode_cell({ r: rowIndex, c: range.s.c + offset })] as
        | import("xlsx").CellObject
        | undefined;
      const value = cellToString(XLSX, cell);
      if (value !== "") any = true;
      record[header] = value;
    });
    if (any) rows.push(record);
  }
  return rows;
}

export function workbookFromModule(XLSX: XlsxModule, data: ArrayBuffer | Buffer): ParsedWorkbook {
  const book = XLSX.read(data, { type: data instanceof ArrayBuffer ? "array" : "buffer" });
  const take = (name: string) => rowsFromSheet(XLSX, book.Sheets[name]);
  const missing = Object.values(SHEET_NAMES).filter((name) => !book.SheetNames.includes(name));
  return {
    sheetNames: book.SheetNames,
    missing,
    sermons: take(SHEET_NAMES.sermons),
    scripture: take(SHEET_NAMES.scripture),
    worshipSongs: take(SHEET_NAMES.worshipSongs),
    songList: take(SHEET_NAMES.songList),
    topics: take(SHEET_NAMES.topics),
  };
}

export async function parseWorkbookArrayBuffer(data: ArrayBuffer): Promise<ParsedWorkbook> {
  const XLSX = await import("xlsx");
  return workbookFromModule(XLSX, data);
}

export function isNoteRow(row: SheetRow): boolean {
  const first = Object.values(row)[0] ?? "";
  return first.startsWith("Excluded:");
}

export function rowNeedsVerify(row: SheetRow): boolean {
  const blob = Object.values(row).join("\n").toLowerCase();
  if (blob.includes("(verify)")) return true;
  const confidence = (row.Confidence || row["Detection confidence"] || "").toLowerCase();
  return confidence === "low";
}

export function rowMatches(row: SheetRow, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return Object.values(row).some((value) => value.toLowerCase().includes(needle));
}

function counted(entries: Map<string, number>): CountItem[] {
  return [...entries.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function topBooks(rows: SheetRow[]): CountItem[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const book = row.Book?.trim();
    if (!book) continue;
    counts.set(book, (counts.get(book) ?? 0) + 1);
  }
  return counted(counts);
}

export function refsPerMonth(rows: SheetRow[]): CountItem[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const month = (row["Stream date"] ?? "").slice(0, 7);
    if (!/^\d{4}-\d{2}$/.test(month)) continue;
    counts.set(month, (counts.get(month) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([label, count]) => ({ label, count }));
}

export function topSongs(rows: SheetRow[]): CountItem[] {
  const items: CountItem[] = [];
  for (const row of rows) {
    if (isNoteRow(row)) continue;
    const title = row["Official title"]?.trim();
    if (!title) continue;
    const times = Number(row["Times sung (streams)"]);
    items.push({ label: title, count: Number.isFinite(times) && times > 0 ? times : 1 });
  }
  return items.sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}
