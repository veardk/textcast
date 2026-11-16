---
name: textcast
description: Turn a YouTube / Bilibili video link, a subtitle file (.srt/.vtt/.json), or a text document (.md/.txt, or text extracted from PDF / web pages) into a self-contained HTML reading page — every original line in chronological order, with original / translation / bilingual modes, collapsible topic cards with analysis, verified timestamps, click-to-seek playback, and an optional summary page. Use when the user wants to read, translate, or deeply understand a video, podcast, or long text without missing any content.
---

# Textcast

Pipeline: **Ingest → IR → Enrich → Render → Open**.

| Stage | Who | Output |
|---|---|---|
| Ingest | `scripts/textcast.py ingest` | `ir.json`: cues + sentence segments with real timestamps |
| Enrich | **you, directly, in this conversation** | `enrich.json` (languages, topics, analysis, summary) + `translations/*.json` |
| Audit | `scripts/textcast.py audit` | completeness / ordering / translation coverage check |
| Publish | `scripts/textcast.py publish` | `textcast/output/<category>/NN-<slug>.html` (mode 1) and/or `NN-<slug>-summary.html` (mode 2), plus the rebuilt `textcast/output/index.html` |
| Open | `npx -y textcast-chat-axi@latest` | the published page in a local reading window with the conversation panel and video player — always run after publishing |

Scripts do everything deterministic (fetching, parsing, segmenting, timing, coverage). You do
the language work **yourself, right here**: choosing languages, topic boundaries, paragraphs,
analysis, translation, summary. You are the translator — nothing else in this pipeline translates.
The data contract is in `references/ir-schema.md` — read it before writing `enrich.json`.

Run scripts with `python3 <skill-dir>/scripts/textcast.py …`. Every path below (`textcast/output/…`)
is relative to the folder you are working in, never the skill folder: the library goes to
`./textcast/output/` there, and the scripts create it on first use. Requirements: Python ≥ 3.10 and
Node ≥ 22 (the channel fetch scripts and `textcast-chat-axi`); `yt-dlp` is only the YouTube fallback. No other dependencies.

## Hard rules

1. **Never omit or rewrite original text.** The page renders original text from the IR, so
   your job is to cover every segment with topics (automatic) and with translations (audit-checked).
2. **Strict chronological order.** Topics are defined only by `from_seg`, strictly increasing,
   starting at 0. Never reorder by importance. If two themes interleave, merge them into one topic.
3. **Timestamps come from the IR only.** Never type times into `enrich.json`.
4. **Caption gaps are facts, not summaries.** `gap_notes` may only name a cause the source
   establishes (music, ad, silence); otherwise leave it out and the page says the track has no text.
5. **Translate it yourself, directly.** Read each segment and write its translation as a skilled
   human translator would: idiomatic, natural in the target language, faithful to what was
   meant — not word-for-word. Keep names, products and terms as spoken. One segment in, one
   translation out — never merge or split segments. Use the target language's own punctuation
   (full-width `，。：；？！` for Chinese/Japanese).
6. **Never hand translation (or analysis) to anything else.** Do not start a sub-agent / Task /
   delegate, do not call a translation service or API (Google, DeepL, an LLM API, a translation
   MCP or plugin), do not run a local translation model or tool (argos, ctranslate2, transformers,
   `trans`, …), and do not write a script that translates. The fastest and correct way is to
   translate the text yourself, batch by batch, in this conversation.

## Workflow

### 0. Collect inputs

- **Source**: URL, subtitle file, or text file. For PDF / web articles, extract the body text
  into a `.md` file yourself (keep paragraphs), then ingest that file.
- **Target language**: ask if the user did not say; default to the user's language.
- **Mode**: `transcript` (mode 1, default), `summary` (mode 2), or `both` (two linked pages).
- **Slug**: the page's name, kebab-case English, 3–6 words that say what the content is
  (e.g. `steve-jobs-stanford-speech`, `standard-agents-spec-talk`). Name it after the content,
  never after the link: no platform names, video IDs or URL parts (`youtube-3krz7rdd4ji` is wrong;
  `publish` refuses it).
- **Folders** (the dot keeps them out of the index): `textcast/output/.work/<slug>/` holds what ingest
  writes (`ir.json`, `source/`), shared by every language; each target language gets its own
  folder inside it, `textcast/output/.work/<slug>/<lang>/`, holding `enrich.json` and `translations/`.
  Below, `<work>` means that language folder, e.g. `textcast/output/.work/standard-agents-spec-talk/zh-CN`.
  Name it with the normalised code: `zh-CN`, `zh-TW`, `en`, `ja`, `fr`, `pt-BR`.
- **Same source again?** Check first:
  `grep -l "<video id or file name>" textcast/output/.work/*/ir.json`. If it is there, do not ingest
  again — add a new language folder beside the existing one (or continue the existing one).

### 1. Ingest

```bash
python3 scripts/textcast.py ingest "<url-or-file>" -o textcast/output/.work/<slug> [--sub-lang en] [--media video.mp4] [--title "…"]
```

- **Naming before you know the title**: with a URL you only learn the title from ingest. Ingest
  into `textcast/output/.work/_new-<a few random letters>` (random, so two sessions never share it), read
  the printed title, then rename the folder to the real slug
  (`mv textcast/output/.work/_new-… textcast/output/.work/<slug>`) before the next step. Ingest refuses to overwrite
  a folder whose languages are already started: re-ingesting can renumber the segments their
  translations are keyed to (each language folder's `ir.lock` records which segments it used).
- **Channel fetchers** (one folder per channel under `scripts/`; `ingest` calls them for you):

  | Channel | Script | Fallback |
  |---|---|---|
  | YouTube | `scripts/youtube/base-youtube-transcript.mjs` (Innertube Android client, no PO token) | `yt-dlp`, used automatically when the script fails or is rate-limited |
  | Bilibili | `scripts/bilibili/base-bilibili-transcript.mjs` (WBI signing, multi-part `?p=N`) | none |

  Both are invoked as `node <script> <url> -f json -o <work>/source/base-<channel>.json`;
  `ingest` reads that JSON (`segments[{start,end,text}]` in seconds) into the IR. Track choice:
  human-made track over auto-generated; language priority is `--sub-lang` →
  English → common languages → first available (pass `--sub-lang` to get the spoken language when
  it is not English).
  `meta.fetcher` records which tool produced the text (shown on the page's provenance card), and
  `meta.fallback_reason` records why yt-dlp was used. Fallback happens silently from the user's
  view except for one `[textcast] … falling back to yt-dlp` line on stderr — mention it.
- **Bilibili login**: subtitles need a logged-in session. The script looks for a cookie in this order:
  `-c` → `BILI_SESSDATA` env → saved cookie → auto-read from the local browser → QR login (opens a
  browser, waits up to 3 min). The cookie is saved in `~/.textcast/`. If ingest fails with a login
  message, ask the user to run once, then retry the ingest:
  `node scripts/bilibili/base-bilibili-transcript.mjs --sync-browser` (or `--login` for QR).
  Do not run the QR login yourself without telling the user — it opens a browser window.
- If a channel fails entirely, report the exact error and ask for a subtitle file; never invent text.
- Local audio/video transcription (faster-whisper) is **not implemented yet**. If the user has
  a subtitle file for it, ingest that with `--media <file>` to keep click-to-seek.
- **Symbols are not text.** `ingest` strips caption/markup symbols (`>>`, leading `-`, `[Music]`, `♪`,
  markdown `**`/bullets/links) so only the words remain; a speaker change is only remembered as a hint
  (`»` in `show` output marks it, for your speaker/paragraph judgment — never copy it into translations).
- Report title, duration, subtitle kind and segment count to the user.

### 2. Set the languages

Confirm `source_lang` (from `source_lang_guess`) and `target_lang`, and write them alone as the
first `<work>/enrich.json`, e.g. `textcast/output/.work/<slug>/zh-CN/enrich.json` containing
`{"source_lang": "en", "target_lang": "zh-CN"}`. Do not read or plan the
content yet — translating it is the reading pass, and the plan comes after.

### 3. Translate first (when source and target languages match, read instead)

You translate, directly — no sub-agent, no translation tool or API, no local model, no script
(hard rule 6). List what is still untranslated:

```bash
python3 scripts/textcast.py show <work> --untranslated
```

Read the listed segments, translate them yourself into natural, idiomatic target-language prose
(read the neighbouring segments when a sentence is split across two), and write the result to the
next `<work>/translations/NNN.json` (`{"<id>": "<translation>"}`) with the file-write tool. Repeat
until the command reports 0 untranslated. The command sizes each batch by text length (about
12 000 characters of English); keep that size.

**Keep the thinking short.** Go straight from the listed segments to the file write: do not
summarise or paraphrase the content in your thinking, and do not plan topics, analysis or
paragraphs while translating. The translation you write is your understanding of the content;
you will not need a second pass over the original.

When source and target languages match there is nothing to translate: page through the content
once with `show --from 0 --count 150` instead, with the same rule — read, do not narrate it.

### 4. Plan and write enrich.json

You have now read everything once, through your own translations. Plan from that, briefly —
decide and write; do not walk through the content again in your thinking, segment by segment.

Add to `enrich.json`: `title` (in target language), `tagline`, `speakers`, `topics`, `paragraphs`
and, for summary modes, `summary`.

- **Speakers**, if identifiable from the content (captions carry no speaker labels; do not guess
  names that are not established — use roles like 主持人 / 嘉宾 instead).
- **Topic boundaries**: roughly 1 topic per 4–8 minutes of video (8–15 for an hour), or per
  section of a text. A boundary goes where a new question, tool, claim or section begins.
  Choose them once; do not deliberate between alternative splits.
- **Topics**: the title captures the non-obvious insight; `analysis` is a real interpretation in
  the target language — claims, reasoning, implications, practical takeaways — not a summary.
- **Summary** (summary modes): `one_sentence`, 4–8 `key_points`, 3–5 `dimensions` such as
  核心论点 / 论证结构 / 关键概念 / 争议与局限 / 可行动建议. The summary page reuses the topics as its
  chapter outline, so do not write a separate outline.
- **Paragraphs**: the segment ids that open a new paragraph, strictly increasing, like the
  natural paragraphs of a printed book (one idea or one turn of the argument each, typically 3–6
  segments; not one per speaker change and not one per sentence). Auto-captions carry no
  paragraph information, so this is your judgment. Paragraphs only change line breaks — never
  text. Topic boundaries and caption gaps always start a new paragraph on their own. Without
  `paragraphs`, a reading-rhythm heuristic is used.

Check the outline: `python3 scripts/textcast.py show <work> --topics`.

### 5. Audit

```bash
python3 scripts/textcast.py audit <work> --mode <mode>
```

Fix every audit error and re-run; publishing refuses while errors remain.
(`render <work>` writes a throwaway preview into the language folder if you need one.)

### 6. Choose a category and publish

Every published page lives in a category folder, and `textcast/output/index.html` shows one card per
category. First look at what already exists:

```bash
python3 scripts/textcast.py categories textcast/output
```

- If an existing category clearly fits the content's subject, reuse its slug.
- Otherwise create one: pick a kebab-case slug for the subject area (e.g. `ai-engineering`,
  `startup-stories`, `history-of-science`) — broad enough to hold future pages, not a one-off —
  and a short display title in the user's language. Do not create near-duplicates of existing
  categories.

```bash
python3 scripts/textcast.py publish <work> --category <category-slug> \
  [--category-title "显示名"] [--category-desc "一句话说明"] --mode <mode>
```

`publish` creates the folder if needed, numbers the page within its category (`01-`, `02-` …;
re-publishing the same slug keeps its number and replaces its files; a language other than the
site's gets its own page, `NN-<slug>-<lang>.html`), records it in
`<category>/category.json`, and rebuilds `textcast/output/index.html`. Slugs and category names that are not
kebab-case are rejected. The index page language is fixed by the first publish; change it with
`python3 scripts/textcast.py index textcast/output --ui-lang <lang>`.

### 7. Deliver

Run step 8's open command first, without asking. Your delivery message: the absolute paths of the
generated pages and of `textcast/output/index.html`, and that the reading window is open. That window is the
deliverable: for video sources it is also the in-page player (clicking a line plays YouTube /
Bilibili in a floating player). Opened directly as a file, YouTube clicks jump to the video in a new
tab (YouTube blocks embeds on `file://`); `python3 scripts/textcast.py serve textcast/output` is only for
in-page playback without the conversation.

When the user asks to tidy up, `python3 scripts/textcast.py clean textcast/output` lists unpublished work
folders, never-renamed `_new-…` folders and leftover previews. Show the list and add `--delete`
only after the user confirms — a recent folder may be another session's work in progress.

### 8. Open the reading window (always, right after publishing)

Every successful publish ends by opening the page with
[textcast-chat-axi](https://github.com/veardk/textcast-chat-axi), run with `npx -y
textcast-chat-axi@latest` (no install). This step is required, not an offer: run the open command without
asking. It returns at once and the window appears. Open the transcript page (`NN-<slug>.html`),
not the summary — the summary is one click away inside the window. If `@latest` cannot be fetched
(network error, or no output for about a minute), retry once with the copy already on this
machine: `npx -y --offline textcast-chat-axi` with the same arguments, and use that form for the
rest of the session. Skip the step only when the user said not to open anything, or when both
forms fail (then report the error and the page paths). When you re-publish after a change in this
same session, do not open again: the window reloads by itself.

**Answer first, then listen.** First write the full delivery message (step 7) as visible text,
ending with one line: the window is listening, and when they are done talking there they can click
**End session** in its ⋮ menu. Then run the poll command in the foreground, as the open output's
`next_step` says, and keep following `next_step` (when to reply, keep polling, or stop).

One command opens the published page in a local window with a conversation panel and, for YouTube / Bilibili pages, a floating video player
that plays from the clicked line. The user clicks or selects text to ask or leave notes, and you
receive them with exact locations. The page file itself is unchanged, so opened directly it is
still the plain reading page.

```bash
npx -y textcast-chat-axi@latest textcast/output/<category>/NN-<slug>.html      # open or resume the review
npx -y textcast-chat-axi@latest poll textcast/output/<category>/NN-<slug>.html # wait for notes; never kill it
```

Follow the `next_step` text the tool prints (when to reply, keep polling, or stop); it is the
authority on the loop. Each note carries a `selector` that tells you what it points at:

| Selector | Means | Edit |
|---|---|---|
| `span#seg<N>-tgt-<mode>` | translation of segment N | the `"<N>"` key in whichever `translations/NNN.json` holds it |
| `span#seg<N>-src-<mode>` | original text of segment N | never edit; if the user reports a caption error, say the original is kept as captured |
| `details#topic-<N> …` | topic card N (1-based): title, brief or analysis paragraph | `enrich.json` → `topics[N-1]` |
| anything else | hero, summary page, etc. | match the quoted `text` to the `enrich.json` field |

- A question (not a change request): answer it in the reply, edit nothing.
- A change: edit only `translations/*.json` or `enrich.json` (hard rules still apply: one
  segment in, one out; topics stay chronological), run `audit`, then re-run the same `publish`
  command (same category and `--mode`). Re-publishing keeps the file path, so the review page
  reloads by itself. Then reply with what changed (segment ids) through `poll --agent-reply`, run
as above.
- When the user ends the session (**End session**), stop and summarize the changes in chat. Do not
  reopen it uninvited. The window stays readable and shows a text the user can copy into any agent
  to reconnect; it runs the open command with `--reopen`.

## Page behaviour (for reference when answering questions)

- Page chrome (buttons, labels, footer) is in the target language, matching the analysis you
  write — strings live in `templates/i18n.json` (zh, zh-Hant, en, ja, ko, fr, de, es, pt, it, ru, ar,
  hi, vi, th, id, tr; others fall back to en). Arabic (and other RTL targets) get a mirrored RTL layout.
  Set `ui_lang` in enrich.json only if the user explicitly wants a different UI language.
- Colour themes 浅色 / 暗色 / 护眼 (light / dark / sepia) via the switch at the top; follows the
  system until the reader picks one, then remembers it.
- Reading modes **原文 / 译文 / 双语对照** (bilingual default); hidden when no translation.
- Topic cards are collapsible (toggle at the card's top-right); each has the analysis, then the
  full original text.
- Timed sources: left gutter shows paragraph start/end; hovering a sentence shows its exact
  time and highlights its counterpart; clicking a sentence or time seeks the player.
- Caption gaps ≥ 15 s are marked automatically (≥ 60 s more prominently).
- Text sources render as 精读版式: paragraph numbers instead of times, no player.

## Page templates

The page layouts are `templates/transcript.html`, `templates/summary.html` and `templates/index.html`.
Each one is a complete HTML page. Open it in a browser and it shows sample content, so you can
change the layout by editing the HTML or `base.css` without touching any Python.

The scripts only fill in data. They use `{{name|sample}}` values and the `@each`, `@if` and
`@sample` comment blocks; the syntax is documented at the top of `scripts/tc_template.py`.

When a page is generated, `base.css`, `theme-init.js` and `reader.js` are inlined into it, so every
output page is still a single self-contained file. `preview.js` is used only for previewing a
template and is never included in output pages.

## Not yet implemented

Local audio/video ASR (faster-whisper).
