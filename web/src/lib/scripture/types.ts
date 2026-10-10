export type LanguageMap = {
  language: string;
  name: string;
  books: { name: string; aliases: string[]; ambiguous: boolean }[];
  bare_skip_aliases: string[];
  number_words: {
    units: Record<string, number>;
    tens: Record<string, number>;
    hundred: string | null;
  };
  chapter_cues: string[];
  verse_cues: string[];
  range_cues: string[];
};

export type MergedMap = {
  order: string[];
  aliases: Record<string, string[]>;
  ambiguous: string[];
  bareSkip: string[];
  units: Record<string, number>;
  tens: Record<string, number>;
  hundred: string | null;
  chapterCues: string[];
  verseCues: string[];
  rangeCues: string[];
};

export type ScriptureHit = {
  ref: string;
  book: string;
  conf: "high" | "medium" | "low";
  why: string;
  span: string;
};
