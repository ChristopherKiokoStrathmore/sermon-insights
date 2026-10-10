import type { LanguageMap, MergedMap } from "./types";

function extendUnique(bucket: string[], items: string[]) {
  for (const item of items) {
    if (!bucket.includes(item)) bucket.push(item);
  }
}

/** Earlier maps win book order and number-word clashes. Aliases and cues are unions. */
export function mergeMaps(maps: LanguageMap[]): MergedMap {
  if (maps.length === 0) {
    throw new Error("at least one language map is required");
  }
  const aliases: Record<string, string[]> = {};
  const ambiguous: string[] = [];
  const order: string[] = [];
  const units: Record<string, number> = {};
  const tens: Record<string, number> = {};
  let hundred: string | null = null;
  const bare: string[] = [];
  const chapter: string[] = [];
  const verse: string[] = [];
  const ranges: string[] = [];

  for (const doc of maps) {
    for (const book of doc.books || []) {
      const name = book.name;
      if (!(name in aliases)) {
        aliases[name] = [];
        order.push(name);
      }
      for (const alias of book.aliases || []) {
        const key = String(alias).trim().toLowerCase();
        if (key && !aliases[name].includes(key)) aliases[name].push(key);
      }
      if (book.ambiguous && !ambiguous.includes(name)) ambiguous.push(name);
    }
    extendUnique(
      bare,
      (doc.bare_skip_aliases || []).map((alias) => String(alias).toLowerCase()),
    );
    const words = doc.number_words || { units: {}, tens: {}, hundred: null };
    for (const [key, value] of Object.entries(words.units || {})) {
      const folded = String(key).toLowerCase();
      if (!(folded in units)) units[folded] = Number(value);
    }
    for (const [key, value] of Object.entries(words.tens || {})) {
      const folded = String(key).toLowerCase();
      if (!(folded in tens)) tens[folded] = Number(value);
    }
    if (hundred == null && words.hundred) hundred = String(words.hundred).toLowerCase();
    extendUnique(chapter, (doc.chapter_cues || []).map((cue) => String(cue)));
    extendUnique(verse, (doc.verse_cues || []).map((cue) => String(cue)));
    extendUnique(ranges, (doc.range_cues || []).map((cue) => String(cue)));
  }

  return {
    order,
    aliases,
    ambiguous,
    bareSkip: bare,
    units,
    tens,
    hundred,
    chapterCues: chapter,
    verseCues: verse,
    rangeCues: ranges,
  };
}
