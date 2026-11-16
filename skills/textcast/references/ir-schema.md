# Textcast data contract

Site layout under `textcast/output/` in the folder the Skill is run from:

```
textcast/output/
├── index.html                       # index page: project hero + one card per category (rebuilt by publish)
├── textcast.json                    # site settings: {"ui_lang": "zh-CN"}
├── .work/<slug>/                    # one folder per source (hidden from the index)
│   ├── ir.json                      # written by `textcast.py ingest` — never edit by hand
│   ├── source/                      # downloaded subtitle track (online sources)
│   └── <lang>/                      # one folder per target language: zh-CN, fr, pt-BR …
│       ├── enrich.json              # written by you (the executing model)
│       ├── translations/*.json      # written by you, in batches
│       └── ir.lock                  # written by the scripts: which segments this language uses
└── <category>/                      # kebab-case, one folder per category
    ├── category.json                # {"slug", "title", "description", "items": [...]}
    ├── 01-<slug>.html               # mode 1 (展示)
    ├── 01-<slug>-summary.html       # mode 2 (总结)
    └── 02-<slug>-fr.html            # the same source in a language other than the site's
```

- `<slug>` names the content in 3–6 English kebab-case words, never the link or video ID;
  `publish` refuses names like `youtube-3krz7rdd4ji`.
- The language folder is the `<work>` argument of `show`, `audit`, `render` and `publish`. Its
  name must equal the normalised `target_lang` (`zh` / `zh-cn` / `zh-Hans` → `zh-CN`,
  `zh-Hant` → `zh-TW`, `pt_br` → `pt-BR`); every command normalises the codes in `enrich.json`
  the same way, so `category.json` always carries one spelling per language.
- `ir.lock` holds a fingerprint of the segment ids and texts, written the first time a command
  reads the language folder. If `ir.json` changes afterwards (a re-ingest with different
  segmentation), every command refuses that language rather than pairing old translations with
  renumbered segments. `ingest` itself refuses to overwrite a source folder whose languages are
  started, unless `--force`.
- `textcast.py clean textcast/output` lists unpublished source or language folders, `_new-…` folders left
  by an unrenamed ingest, render previews and `.DS_Store`; `--delete` removes them.

`category.json` items carry `number`, `slug`, `title`, `tagline`, `source_type`, `source_url`,
`duration_ms`, `source_lang`, `target_lang`, `transcript`, `summary`, `published`, `work`; the index
is rendered from these files only (entries whose HTML was deleted are skipped).

## ir.json (Ingest output)

```jsonc
{
  "version": 1,
  "meta": {
    "source_type": "youtube | bilibili | subtitle | text",
    "title": "…", "uploader": "…", "upload_date": "YYYYMMDD",
    "source_url": "…", "video_id": "…", "bili_page": 1,
    "duration_ms": 1234000,              // null for text
    "has_timestamps": true,              // false → 精读版式 (no gutter times, no player)
    "fetcher": "base-youtube-transcript | base-bilibili-transcript | yt-dlp",  // online sources
    "fallback_reason": "why yt-dlp replaced the base script",                   // only on fallback
    "subtitle_kind": "manual | auto | file | none",
    "subtitle_lang": "en", "subtitle_file": "source/base-youtube.json",
    "media_file": "/abs/path/video.mp4", // optional (--media), enables in-page seek
    "source_lang_guess": "en"            // heuristic; you decide enrich.source_lang
  },
  "cues": [ { "i": 0, "start_ms": 1200, "end_ms": 3400, "text": "raw subtitle cue" } ],
  "segments": [
    { "id": 0, "cues": [0, 2], "start_ms": 1200, "end_ms": 6100, "text": "cues 0–2 joined" }
  ]
}
```

- **cues** are the source units (subtitle cues, or paragraphs for text), **cleaned of non-text symbols**:
  speaker-change marks (`>>`, a leading `-`), sound tags (`[Music]`, `♪`, a whole-cue `(applause)`) and
  markdown syntax (`**bold**`, links, bullets, rules) are removed. A speaker change is kept as
  `"turn": true` on the cue that starts the new speaker; a cue holding a mid-cue `>>` is split there
  (inner boundary time is proportional to text length, within the original cue's range). Spoken
  words, including fillers like "uh", are never removed. The untouched track stays in `source/`.
- **segments** are sentence-sized reading units built deterministically from cues. Every cue
  belongs to exactly one segment, in order. A cue with `turn` always starts a new segment, which
  carries `"turn": true` — a hint about the source captions, not a paragraph rule (no symbol is shown). Segments are what you translate, what
  topics and speakers snap to, and what the page highlights and seeks.
- Segment text and times always come from the IR. You never re-type original text or
  timestamps, so completeness and time accuracy hold by construction.

## enrich.json (written by you)

```jsonc
{
  "source_lang": "en",          // required; BCP-47-ish (en, zh-CN, ja …)
  "target_lang": "zh-CN",       // required; same as source → no translation, no mode switch
  "ui_lang": "en",              // optional; page chrome language, defaults to target_lang
                                // (17 bundles in templates/i18n.json; anything else → en)
  "title": "localized page title",          // optional, defaults to meta.title
  "tagline": "one-line hook",               // optional
  "speakers": [                             // optional; ranges by segment id
    { "from_seg": 0, "name": "主持人 Lex" },
    { "from_seg": 14, "name": "嘉宾 Karpathy" }
  ],
  "topics": [                               // required; chronological, contiguous
    {
      "from_seg": 0,                        // first topic MUST be 0; strictly increasing
      "title": "non-obvious insight, not a surface label",
      "brief": "one sentence",
      "analysis": ["paragraph, **bold** = highlight", "…"]
    }
  ],
  "paragraphs": [0, 4, 9],                  // optional: segment ids that open a paragraph (book-like
                                            // natural paragraphs); omitted → reading-rhythm heuristic
  "gap_notes": { "37": "片头音乐" },        // optional: cause of the ≥15s gap before segment 37,
                                            // only when the source establishes it
  "summary": {                              // required for --mode summary|both
    "one_sentence": "…",
    "key_points": ["…", "…"],
    "dimensions": [ { "title": "论证结构", "paragraphs": ["…"] } ]
  },
  "translations": { "0": "…" }              // optional; prefer translations/*.json batches
}
```

A topic owns segments `[from_seg, next.from_seg)`; the last topic runs to the end. Topics
therefore cannot overlap or leave holes. Speaker ranges work the same way.

## translations/*.json

Plain `{ "<segment id>": "translated text" }` maps in `<lang>/translations/`. All files are merged
in filename order (later wins), then layered over `enrich.translations`. Write one file per batch,
e.g. `translations/001.json`, `translations/002.json`. There is no size limit per file; `show
--untranslated` sizes each batch by text length (`--max-units`, default 12000 reading units,
a CJK character counting as 3), so batches are even in work, not in segment count. A file that is
not valid JSON stops every command with its path.

## What `audit` enforces

- Layout: the language folder is named after the normalised `target_lang`, and `ir.json` still
  matches its `ir.lock`.
- IR integrity: segments cover all cues contiguously.
- `source_lang` / `target_lang` present.
- Topics: non-empty, first `from_seg` is 0, strictly increasing, in range, each with title and
  analysis (brief is a warning).
- Speakers: increasing `from_seg`. Paragraphs: integer ids, increasing, in range.
- When languages differ: every segment has a non-empty translation; no unknown ids.
- Summary modes: `summary.one_sentence` and `summary.key_points` present.

`render` runs the same audit and refuses to write pages while errors remain.
