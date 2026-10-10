import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import exodusSnippet from "../../data/exodus-snippet.json";
import { displayRef, findText, indexFor } from "./match";
import type { LanguageMap } from "./types";

const CASES: [string, string, string][] = [
  ["Mwanzo sura ya kwanza mstari wa kwanza", "Genesis 1:1", "high"],
  ["Zaburi 23", "Psalms 23", "medium"],
  ["zaburi sura ya 23 mstari wa kwanza", "Psalms 23:1", "high"],
  ["Wakorintho wa kwanza kifungu cha 13 mstari wa nne", "1 Corinthians 13:4", "high"],
  ["Wakorintho wa kwanza kifungu cha kumi na tatu mstari wa nne", "1 Corinthians 13:4", "high"],
  ["Zaburi sura ya ishirini na tatu mstari wa kwanza", "Psalms 23:1", "high"],
  ["Zaburi sura ya Ishirini na tatu mstari wa kwanza", "Psalms 23:1", "high"],
  ["Yohana sura ya 3 mstari wa 16", "John 3:16", "high"],
  ["John 3:16", "John 3:16", "high"],
  ["Marko 1:1", "Mark 1:1", "high"],
  ["Kutoka 20", "Exodus 20", "medium"],
  ["kitabu cha Isaya sura ya 43 mstari wa 16 hadi 21", "Isaiah 43:16-21", "high"],
  ["2 Samweli sura ya 6", "2 Samuel 6", "medium"],
  ["Luka 18:35-43", "Luke 18:35-43", "high"],
  ["Ufunuo", "Revelation", "low"],
  ["Psalms 119:177", "Psalms 119:177", "low"],
];

describe("scripture matcher", () => {
  it("normalises the Exodus 17:8-16 caption fixture", () => {
    const fixturePath = path.resolve(
      import.meta.dirname,
      "../../../../tests/fixtures/transcript_snippet.json",
    );
    const payload = JSON.parse(readFileSync(fixturePath, "utf8")) as {
      segments: { text: string }[];
    };
    const text = payload.segments.map((segment) => segment.text).join(" ");
    expect(exodusSnippet.text).toBe(text);
    const hits = findText(text);
    const high = hits.filter((hit) => hit.ref === "Exodus 17:8-16");
    expect(high.length).toBeGreaterThan(0);
    expect(high[0]?.conf).toBe("high");
    expect(high[0]?.book).toBe("Exodus");
    expect(high[0]?.why).toBe("");
  });

  it.each(CASES)("reads %s as %s (%s)", (text, ref, conf) => {
    const hits = findText(text);
    expect(hits.length, text).toBeGreaterThan(0);
    expect(hits[0]?.ref).toBe(ref);
    expect(hits[0]?.conf).toBe(conf);
  });

  it("skips bare ambiguous names", () => {
    expect(findText("Mark alisema")).toEqual([]);
    expect(findText("Kutoka")).toEqual([]);
    expect(findText("Mwanzo")).toEqual([]);
  });

  it("marks run-together digits for a human check", () => {
    const hits = findText("Exodus 1718");
    expect(hits[0]?.conf).toBe("low");
    expect(hits[0]?.why).toContain("verify");
    expect(hits[0]?.ref).toBe("Exodus 17:18");
    expect(displayRef(hits[0]?.ref ?? "", hits[0]?.conf ?? "")).toMatch(/\(verify\)$/);
  });

  it("accepts an extra language map", () => {
    const extra: LanguageMap = {
      language: "xx",
      name: "Example",
      books: [{ name: "Genesis", aliases: ["mwanzo-xx"], ambiguous: false }],
      bare_skip_aliases: [],
      number_words: { units: { kwanza: 1 }, tens: {}, hundred: null },
      chapter_cues: ["sura"],
      verse_cues: ["mstari"],
      range_cues: ["hadi"],
    };
    const hits = findText("mwanzo-xx sura 1 mstari kwanza", ["xx"], [extra]);
    expect(hits[0]?.ref).toBe("Genesis 1:1");
    expect(hits[0]?.conf).toBe("high");
  });

  it("lists the Kiswahili canon in order", () => {
    const index = indexFor(["sw"]);
    expect(index.order).toContain("Genesis");
    expect(index.order).toContain("Revelation");
    expect(index.order.indexOf("1 John")).toBeLessThan(index.order.indexOf("2 John"));
    expect(index.order.indexOf("2 John")).toBeLessThan(index.order.indexOf("Jude"));
    expect(index.order).toHaveLength(66);
  });
});
