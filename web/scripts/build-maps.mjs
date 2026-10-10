/**
 * Compile src/sermon_insights/languages/*.yaml into the JSON the browser matcher loads.
 * Run from web/: node scripts/build-maps.mjs
 */
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { parse } from "yaml";

const languagesDir = path.resolve(import.meta.dirname, "../../src/sermon_insights/languages");
const outFile = path.resolve(import.meta.dirname, "../src/lib/scripture/maps.generated.json");

function lowerMap(value) {
  const out = {};
  for (const [key, number] of Object.entries(value || {})) {
    out[String(key).toLowerCase()] = Number(number);
  }
  return out;
}

function normalize(code, data) {
  const words = data.number_words || {};
  return {
    language: data.language || code,
    name: data.name || code,
    books: (data.books || []).map((book) => ({
      name: book.name,
      aliases: (book.aliases || [])
        .map((alias) => String(alias).trim().toLowerCase())
        .filter(Boolean),
      ambiguous: Boolean(book.ambiguous),
    })),
    bare_skip_aliases: (data.bare_skip_aliases || []).map((alias) => String(alias).toLowerCase()),
    number_words: {
      units: lowerMap(words.units),
      tens: lowerMap(words.tens),
      hundred: words.hundred ? String(words.hundred).toLowerCase() : null,
    },
    chapter_cues: (data.chapter_cues || []).map((cue) => String(cue)),
    verse_cues: (data.verse_cues || []).map((cue) => String(cue)),
    range_cues: (data.range_cues || []).map((cue) => String(cue)),
  };
}

const languages = {};
for (const filename of readdirSync(languagesDir).filter((name) => name.endsWith(".yaml")).sort()) {
  const code = filename.replace(/\.yaml$/, "");
  const data = parse(readFileSync(path.join(languagesDir, filename), "utf8")) || {};
  if (!data.books) {
    throw new Error(`${filename} has no books list`);
  }
  languages[code] = normalize(code, data);
}

const payload = {
  generatedFrom: "src/sermon_insights/languages",
  languages,
};

writeFileSync(outFile, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`wrote ${outFile} (${Object.keys(languages).join(", ")})`);
