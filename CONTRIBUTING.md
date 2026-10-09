# Contributing

sermon-insights is a small package with one job: public videos in, a workbook of sermon and worship notes out. Changes should keep that job honest. A match the audio did not earn is a bug, even when the verse "looks right".

## Setup

```bash
python -m pip install -e ".[dev]"
ruff check src tests scripts
pytest
```

Python 3.11 or 3.12. Tests do not use the network. If a test needs a subprocess, give it a fake runner; do not shell out to yt-dlp.

Do not commit audio, `*.duckdb`, channel dumps, cookies, tokens, Drive file ids, or a full transcript from a real service. `data/`, cache directories, and `songcache.json` at the repo root are gitignored for that reason. The synthetic fixture in `samples/offline/fixture/` is the one transcript that belongs in git. Keep new samples the same size and the same kind of fiction: no real channel handle, no preacher's name.

Commit messages should describe the change. Do not add `Co-authored-by` trailers.

## Add a language map

Scripture book names are data, not code. Kiswahili is `src/sermon_insights/languages/sw.yaml`. English is `en.yaml` beside it. A new language is another file in that directory, named with the code you will put in config: `fr.yaml` for `languages: [sw, fr]`.

Earlier codes in the config list win when two maps disagree about canon order or about a number word. Aliases and cue fragments are unions, so `fr` added after `sw` keeps every Kiswahili alias.

Minimum shape, the same keys `sw.yaml` uses:

```yaml
language: fr
name: Français
books:
  - name: Genesis          # English canon name. This is the name written to the sheet.
    aliases: [genèse, genese, genesis]
    ambiguous: false       # true if the bare name is also an ordinary word
  - name: Psalms
    aliases: [psaumes, psaume]
    ambiguous: false
  # ...one entry per book you want this language to recognise
bare_skip_aliases: []      # aliases that must not match unless a number follows
number_words:
  units:                   # matched case-insensitively
    un: 1
    deux: 2
  tens:
    dix: 10
    vingt: 20
  hundred: cent            # or omit
chapter_cues:              # regex fragments, joined with |
  - chapitre
verse_cues:
  - verset
range_cues:
  - à
  - "-"
```

Notes that are easy to get wrong:

- `name` is the English book the rest of the pipeline sorts and prints. Reuse the names already in `sw.yaml` (`1 Corinthians`, `Psalms`, `Song of Solomon`, …) so a French alias and a Swahili alias land on the same row.
- Put the longer alias first in your head, but you do not have to sort the YAML. The matcher sorts aliases by length and tries the longer one first, so `wakorintho wa kwanza` wins over `wakorintho`.
- `ambiguous: true` plus an entry in `bare_skip_aliases` is how Mark, John, Luka, Mwanzo, and Kutoka avoid firing on a person's name. If the bare word is safe, leave both off.
- `chapter_cues`, `verse_cues`, and `range_cues` are regular-expression fragments. Write `sura\s+ya` if you need a flexible space. A plain word is fine when the word itself is the cue.
- Number words are folded to lower case before lookup. `Ishirini na tatu` and `ishirini na tatu` both parse as 23. That is deliberate: an uppercase number word used to be dropped and the verse collapsed to whatever digit remained.
- High confidence still requires a chapter cue and a verse cue (or digits in those slots). A book and a chapter with no verse stays medium. A book alone, a chapter past the book's length, a verse above 176, or a run of digits like `1718` stays low and the workbook prints `(verify)`.

You can try a map without copying it into the package. `load_map` and `find` take `extra_dirs`:

```python
from sermon_insights.scripture import find

hits = find(
    "genèse chapitre 1 verset 1",
    languages=["fr"],
    extra_dirs=["./my-maps"],
)
```

`tests/test_scripture.py` (`test_extra_language_map`) is the pattern: write a tiny YAML in `tmp_path`, call `find`, assert the English reference and the confidence. Add a case for your language next to it, using one real sentence shape from that tradition, and a case that must stay low or must be skipped.

Then set the config:

```yaml
languages: [sw, fr]
```

Run `pytest tests/test_scripture.py` and `ruff check`.

Whisper's `whisper.language` is a separate setting (a faster-whisper language code). The book map does not select the ASR language.

## Themes and songs

Keyword themes live in `src/sermon_insights/data/themes.yaml`. A new theme needs a `name`, a `pattern`, and `seeds`. The seeds are what BERTopic is nudged toward when the `[topics]` extra is installed; the pattern is what runs otherwise. Say which one you used in the Theme method column by leaving that labelling to `assign_themes`. Do not hard-code a theme onto a video id.

Song phrases belong in the local `songcache.json`, not in the repo, unless they are a tiny synthetic seed like `data/songcache.seed.json`. Confidence stays in `sermon_insights.songs.confidence_for`: two distinct phrases across two windows keep the cache's own confidence; one phrase in one window is `low`.

## Pull requests

Describe what a reader of the workbook will see differently. If you touched detection, scripture, or song confidence, add or adjust a fixture test. CI runs `ruff check src tests scripts` and `pytest` on Python 3.12.
