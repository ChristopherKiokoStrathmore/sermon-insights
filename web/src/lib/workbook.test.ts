import { describe, expect, it } from "vitest";
import sample from "../data/sample-workbook.json";
import { refsPerMonth, topBooks, topSongs, type ParsedWorkbook } from "./workbook";

const workbook = sample as ParsedWorkbook;

describe("sample workbook counts", () => {
  it("counts only the rows that are in the file", () => {
    expect(workbook.sermons).toHaveLength(1);
    expect(workbook.scripture).toHaveLength(2);
    expect(workbook.worshipSongs).toHaveLength(3);
    expect(topBooks(workbook.scripture)).toEqual([
      { label: "1 Corinthians", count: 1 },
      { label: "Psalms", count: 1 },
    ]);
    expect(refsPerMonth(workbook.scripture)).toEqual([{ label: "2025-06", count: 2 }]);
    expect(topSongs(workbook.songList)).toEqual([{ label: "Uongezeke Yesu", count: 1 }]);
  });
});
