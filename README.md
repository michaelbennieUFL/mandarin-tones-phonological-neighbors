# Taiwanese Mandarin phonological lexicon

Search single-character MOE dictionary entries by pronunciation and Chinese Wordnet sense, generate four-tone sets, and index MOE dictionary-entry recordings. The project runs offline once its Python packages and datasets are available.

## Setup

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer, then run `uv sync`. From the repository root, place these trusted source files at the paths in `config/default.yaml` (or edit that file):

- `data/dictionaries/dict_concised_2014_20260929.xlsx`: MOE text database.
- `data/dictionaries/cwn-graph-v.2022.04.22.pyobj`: Chinese Wordnet graph image.
- For audio only, `data/dictionaries/dict_concised_www_2014_20260929.xlsx` and the extracted `dict_concised_www_2014_20260929/www_wav/` directory.

The www archive has five numbered parts; concatenate them in numeric order into a ZIP and extract it. Download the datasets from their official distributors and check their terms. Source datasets, processed data, and output files are excluded from Git. The Cwn image is a Python pickle: **only load an image from a trusted source**. The loader reads its graph directly to avoid the CwnGraph package's automatic online manifest retrieval.

```sh
uv run twlex datasets setup
uv run twlex search --initial-preset voiceless_fricatives --final-preset nasal_coda --tones 1,2,3,4
uv run twlex minimal-sets --initials q,j,x --pos verb --require-four-tones
uv run twlex audio manifest --input output/minimal_sets/results.json
uv run twlex audio extract --input output/minimal_sets/results.json
uv run twlex tui
```

Configuration controls paths, presets, filters, output formats, and POS granularity. Empty filter lists are unrestricted; selections within a dimension are combined with OR, and dimensions with AND. Search and set results are written to `output/` in CSV, JSON and Excel by default. Use `--help` on commands for options. Run `uv run pytest` for tests.

MOE readings and Cwn senses are linked by character, not verified sense-by-reading. Review every such association and independent-word status before using results. Unsupported or unusual Zhuyin is flagged. The phonological representation is a practical analysis, not a substitute for phonetic validation. The `www` recordings are dictionary-entry narration; exact entry ID and headword matches do not establish that the recorded pronunciation matches a particular sense. Audio manifests retain these review flags, and copies leave originals untouched.

MOE materials and Chinese Wordnet data have their own licensing and redistribution conditions; consult the original distributors. CwnGraph software is GPL-3.0. Do not publish third-party datasets or recordings without checking their terms.

## Phonological filters and presets

`search` accepts comma-separated values in `--initials`, `--finals`, `--initial-preset`, `--final-preset`, and `--tones`. Configure the same selections under `filters` in `config/default.yaml`. CLI values replace their corresponding configuration lists. Different lists in the same dimension are combined with OR; initial, final, tone, and POS dimensions combine with AND. Empty lists impose no restriction. Presets can be edited or added in the YAML file.

**Initial values:** `b, p, m, f, d, t, n, l, g, k, h, j, q, x, zh, ch, sh, r, z, c, s`, and the empty string `''` for zero initial. Set zero initial through YAML (`initials: ['']`) or the `zero_initial` preset. Pinyin `y` and `w` are represented as zero initial with a medial or vowel.

| Initial preset | Values |
| --- | --- |
| `sonorants` | m, n, l |
| `voiceless_fricatives` | f, s, sh, x, h |
| `affricates` | z, c, zh, ch, j, q |
| `stops` | b, p, d, t, g, k |
| `aspirated_stops` / `unaspirated_stops` | p, t, k / b, d, g |
| `aspirated_affricates` / `unaspirated_affricates` | c, ch, q / z, zh, j |
| `bilabial_initials` / `labiodental_initials` | b, p, m / f |
| `velar_initials` | g, k, h |
| `nasal_initials` | m, n |
| `retroflex_initials` | zh, ch, sh, r |
| `alveolar_initials` | z, c, s |
| `alveolopalatal_initials` | j, q, x |
| `zero_initial` | empty initial |

**Final values:** `--finals` matches the normalized `phonological_final`, not the spelling in Pinyin. Values observed in the supplied dataset are `a, ai, an, ang, ao, apical, e, ei, en, eng, er, i, ia, iai, ian, iang, iao, ien, ieng, io, iou, iê, o, ou, u, ua, uai, uan, uang, uei, uen, ueng, uo, ü, üan, üen, üeng, üê`. For example, conventional Pinyin `iu` is represented as `iou`, and `un` can appear as `uen` or `üen`. The list reflects the current parser and source data; review unusual values and analyses.

| Final preset | Current criterion |
| --- | --- |
| `nasal_coda` | coda n or ng |
| `alveolar_nasal_coda` / `velar_nasal_coda` | coda n / ng |
| `non_nasal` | empty coda |
| `monophthong` | nucleus a, o, e, i, u, ü |
| `diphthong` | nucleus ai, ei, ao, ou |
| `high_vowels` | nucleus i, u, ü |
| `apical` / `rhotic` | nucleus apical / er |
| `i_medial` / `u_medial` / `ü_medial` | medial i / u / ü |
| `no_medial` | empty medial |
| `open_a_nucleus` | nucleus a |
| `e_nucleus` | nucleus e or ê |

These presets match parser fields literally. A standalone `i`, `u`, or `ü` is a nucleus with no medial, so it matches `no_medial`, not its corresponding medial preset. Multiple fields in a custom final preset are combined with AND; values within a field are combined with OR. Category boundaries are analysis choices, not verified phonetic classifications.

**Tones:** `1` (unmarked Zhuyin), `2` (ˊ), `3` (ˇ), `4` (ˋ), and `5` (neutral tone, ˙). The default is `[1, 2, 3, 4]`; use `--tones 1,2,3,4,5` or edit `filters.tones` to include neutral tone. Four-tone sets use tones 1–4 only.

```sh
uv run twlex search --initial-preset aspirated_stops --final-preset nasal_coda --tones 2,3
uv run twlex search --initials q,x --finals i,ian,ü --tones 1,4
uv run twlex search --initial-preset zero_initial --final-preset i_medial
```
