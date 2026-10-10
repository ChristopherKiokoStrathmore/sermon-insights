/**
 * Browser port of sermon_insights.scripture.
 * Book maps are generated from the YAML; the match rules are the same ones
 * the CLI uses, including low-confidence "(verify)" hits.
 */
import generated from "./maps.generated.json";
import { mergeMaps } from "./merge";
import type { LanguageMap, MergedMap, ScriptureHit } from "./types";

const bundled = generated.languages as Record<string, LanguageMap>;

function escapeRegex(value: string): string {
  return value.replace(/[^A-Za-z0-9]/g, (char) => `\\${char}`);
}

function isDigits(value: string | undefined): boolean {
  return Boolean(value && /^\d+$/.test(value.trim()));
}

export class ScriptureIndex {
  readonly order: string[];
  readonly ambiguous: Set<string>;
  readonly bareSkip: Set<string>;
  readonly units: Record<string, number>;
  readonly tens: Record<string, number>;
  readonly hundred: string | null;
  readonly aliasMap = new Map<string, string>();
  private readonly pattern: RegExp;
  private readonly chapterCue: RegExp;
  private readonly verseCue: RegExp;

  constructor(merged: MergedMap) {
    this.order = merged.order;
    this.ambiguous = new Set(merged.ambiguous);
    this.bareSkip = new Set(merged.bareSkip);
    this.units = merged.units;
    this.tens = merged.tens;
    this.hundred = merged.hundred;

    const pairs: [string, string][] = [];
    for (const book of merged.order) {
      for (const alias of merged.aliases[book] ?? []) pairs.push([alias, book]);
    }
    pairs.sort((left, right) => right[0].length - left[0].length);
    const seen: string[] = [];
    for (const [alias, book] of pairs) {
      this.aliasMap.set(alias, book);
      if (!seen.includes(alias)) seen.push(alias);
    }

    const numberWords = [...Object.keys(this.units), ...Object.keys(this.tens)];
    if (this.hundred) numberWords.push(this.hundred);
    numberWords.push("na");
    const number = `(\\d{1,3}|(?:(?:${numberWords.map(escapeRegex).join("|")})\\b\\s*)+)`;
    const chapter = `(?:${merged.chapterCues.join("|")})`;
    const verse = `(?:${merged.verseCues.join("|")})`;
    const range = `(?:${merged.rangeCues.join("|")})`;
    this.chapterCue = new RegExp(chapter, "i");
    this.verseCue = new RegExp(verse, "i");
    this.pattern = new RegExp(
      `\\b(?:kitabu\\s+cha\\s+)?(${seen.map(escapeRegex).join("|")})\\b[\\s,]*(?:${chapter}\\s+)?${number}?[\\s,:.]*(?:${verse}\\s+(?:ya\\s+|wa\\s+)?)?${number}?(?:\\s*(?:${range})\\s*(?:${verse}\\s+(?:wa\\s+)?)?${number})?`,
      "gi",
    );
  }

  wnum(raw: string | null | undefined): number | null {
    if (raw == null) return null;
    const text = raw.trim();
    if (/^\d+$/.test(text)) return Number(text);
    let total = 0;
    let ok = false;
    for (const word of text.toLowerCase().split(/\s+/)) {
      if (!word || word === "na") continue;
      if (this.hundred && word === this.hundred) {
        total += 100;
        ok = true;
      } else if (word in this.tens) {
        total += this.tens[word];
        ok = true;
      } else if (word in this.units) {
        total += this.units[word];
        ok = true;
      }
    }
    return ok ? total : null;
  }

  find(text: string): ScriptureHit[] {
    const found: ScriptureHit[] = [];
    if (!text) return found;
    this.pattern.lastIndex = 0;
    for (const match of text.matchAll(this.pattern)) {
      const name = (match[1] ?? "").toLowerCase();
      const book = this.aliasMap.get(name);
      if (!book) continue;
      const rawChapter = match[2];
      const rawVerse = match[3];
      const rawEnd = match[4];
      const chapter = rawChapter ? this.wnum(rawChapter) : null;
      const verse = rawVerse ? this.wnum(rawVerse) : null;
      const verseEnd = rawEnd ? this.wnum(rawEnd) : null;
      const span = (match[0] ?? "").trim();
      if (chapter == null) {
        if (this.ambiguous.has(book) || this.bareSkip.has(name)) continue;
        found.push({ ref: book, book, conf: "low", why: "book only", span });
        continue;
      }
      let ref = `${book} ${chapter}`;
      if (verse) {
        ref += `:${verse}`;
        if (verseEnd && verseEnd > verse) ref += `-${verseEnd}`;
      }
      const explicitChapter = this.chapterCue.test(span) || isDigits(rawChapter);
      const explicitVerse = this.verseCue.test(span) || isDigits(rawVerse);
      let confidence: ScriptureHit["conf"];
      let why: string;
      if (explicitChapter && explicitVerse && verse) {
        confidence = "high";
        why = "";
      } else if (verse || explicitChapter) {
        confidence = "medium";
        why = verse ? "chapter/verse not explicitly marked" : "chapter only, no verse";
      } else {
        confidence = "low";
        why = "number may not be a chapter";
      }
      if (verse && verse > 176) {
        confidence = "low";
        why = "implausible verse number";
      }
      if (chapter > 150 || (book !== "Psalms" && chapter > 66)) {
        const raw = (rawChapter ?? "").trim();
        if (/^\d+$/.test(raw) && (raw.length === 3 || raw.length === 4)) {
          const chapterGuess = Number(raw.slice(0, 2));
          let verseGuess = Number(raw.slice(2));
          if (verse) verseGuess = Number(raw.slice(2) + String(verse));
          ref = `${book} ${chapterGuess}:${verseGuess}`;
          if (verseEnd && verseEnd > verseGuess) ref += `-${verseEnd}`;
          confidence = "low";
          why = `run-together digits "${raw}" read as ${chapterGuess}:${verseGuess} - verify (could also be a chapter range)`;
        } else {
          confidence = "low";
          why = "implausible chapter";
        }
      }
      found.push({ ref, book, conf: confidence, why, span });
    }
    return found;
  }
}

export function displayRef(ref: string, confidence: string): string {
  if (confidence === "low" && !ref.includes("(verify)")) return `${ref} (verify)`;
  return ref;
}

export function indexFor(languages: string[] = ["sw", "en"], extras: LanguageMap[] = []): ScriptureIndex {
  const docs = languages.map((code) => {
    const extra = extras.find((map) => map.language === code);
    if (extra) return extra;
    const map = bundled[code];
    if (!map) {
      throw new Error(
        `No scripture map for language ${JSON.stringify(code)}. Add a YAML file under src/sermon_insights/languages and run npm run sync.`,
      );
    }
    return map;
  });
  return new ScriptureIndex(mergeMaps(docs));
}

const defaultIndex = indexFor();

export function findText(text: string, languages?: string[], extras?: LanguageMap[]): ScriptureHit[] {
  const index = languages || extras?.length ? indexFor(languages, extras) : defaultIndex;
  return index.find(text);
}

export function bundledLanguages(): Record<string, LanguageMap> {
  return bundled;
}
