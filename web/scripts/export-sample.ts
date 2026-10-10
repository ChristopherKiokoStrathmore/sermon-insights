/**
 * Turn the committed sample workbook and the Exodus caption fixture into JSON
 * the static site can import. No network.
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as XLSX from "xlsx";
import { workbookFromModule } from "../src/lib/workbook";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const workbookPath = path.join(repoRoot, "samples/example/sermon_insights_sample.xlsx");
const snippetPath = path.join(repoRoot, "tests/fixtures/transcript_snippet.json");
const dataDir = path.join(webRoot, "src/data");

const buffer = readFileSync(workbookPath);
const parsed = workbookFromModule(XLSX, buffer);
const workbookOut = path.join(dataDir, "sample-workbook.json");
writeFileSync(workbookOut, `${JSON.stringify(parsed, null, 2)}\n`, "utf8");

const snippet = JSON.parse(readFileSync(snippetPath, "utf8")) as {
  segments: { text: string }[];
};
const text = snippet.segments.map((segment) => segment.text).join(" ");
const snippetOut = path.join(dataDir, "exodus-snippet.json");
writeFileSync(snippetOut, `${JSON.stringify({ id: "fixture-exodus", text }, null, 2)}\n`, "utf8");

console.log(`wrote ${workbookOut}`);
console.log(`wrote ${snippetOut}`);
