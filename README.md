# Textcast

An Agent Skill that turns a video, a subtitle file or a long text into a self-contained HTML reading page: every original line in order, with a translation beside it, topic cards with analysis, and timestamps that play the video from the line you click.

Your agent does the reading and translating itself, in the conversation. The scripts handle everything deterministic: fetching captions, segmenting, timing, coverage checks and rendering. Nothing is summarised away: the page always keeps the full original text.

## Install

Pick one route per agent. Installing the same Skill twice (for example as a plugin and with `npx skills`) gives your agent two copies.

### Any agent (recommended)

```bash
npx skills@latest add veardk/textcast -g
```

`-g` installs it for your user, so it works in every folder. Add `-a <agent>` to choose the agent up front (`claude-code`, `codex`, `cursor`, `opencode`, `windsurf`, …), or leave it out and pick from the list. To update, run `npx skills@latest update textcast`.

<details>
<summary><strong>Claude Code</strong> (plugin)</summary>

```bash
claude plugin marketplace add veardk/textcast
claude plugin install textcast@veardk
```

To update, run `claude plugin marketplace update veardk`, then `claude plugin update textcast@veardk`.

</details>

<details>
<summary><strong>Codex</strong> (plugin)</summary>

```bash
codex plugin marketplace add veardk/textcast
codex plugin add textcast@veardk
```

Updates itself at startup.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI and VS Code)</summary>

```bash
copilot plugin marketplace add veardk/textcast
copilot plugin install textcast@veardk
```

In VS Code, run **Chat: Install Plugin From Source** and enter `https://github.com/veardk/textcast`.

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/veardk/textcast.git
```

Run it again to update.

</details>

<details>
<summary><strong>Manual</strong> (git clone)</summary>

Clone the repository into your agent's skills folder. For Claude Code:

```bash
git clone https://github.com/veardk/textcast.git ~/.claude/skills/textcast
```

To update, run `git pull` in that folder.

</details>

## Use

Ask your agent, for example:

> Turn https://www.youtube.com/watch?v=… into a Textcast page in Chinese.

> 把这个 PDF 做成双语精读页面。

The agent fetches the source, translates it, groups it into topics, publishes the page and opens it in a reading window where you can ask about any sentence.

## Features

- **Sources**: YouTube and Bilibili links, subtitle files (`.srt`, `.vtt`, `.json`), and text documents (`.md`, `.txt`, or text the agent extracts from a PDF or web page).
- **Full text, in order**: every original segment appears on the page, in chronological order. An audit step checks completeness and translation coverage before publishing.
- **Original / translation / bilingual** reading modes, with hover highlighting between a sentence and its translation.
- **Topic cards** with the agent's analysis, collapsible, each followed by the full original text.
- **Verified timestamps**: times come from the captions only. Clicking a line plays the video from there.
- **Summary page** (optional), linked from the transcript page.
- **A library**: pages are grouped into categories, with an index page listing them all.
- **Themes and languages**: light, dark and sepia themes; page labels in 17 languages, with a right-to-left layout for Arabic.
- **Reading window**: after publishing, the page opens in [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi), a local window with a conversation panel and a floating video player. Select any text to ask the agent about it or request a change.

## Where the pages go

Pages are written to `./textcast/output/` inside the folder where you run your agent, not into the skill folder:

```text
textcast/output/
├── index.html                      # the library
├── <category>/NN-<slug>.html       # transcript page
├── <category>/NN-<slug>-summary.html
└── .work/                          # intermediate files (captions, translations)
```

Every page is a single HTML file that also works when opened directly.

## Requirements

- Python 3.10 or later (standard library only)
- Node.js 22 or later, for the caption fetchers and the reading window (`npx` downloads it on first use)
- `yt-dlp` (optional), used automatically when the YouTube fetcher fails
- Bilibili captions need a logged-in session. The fetcher reads the cookie from your browser or offers a QR login, and saves it in `~/.textcast/`.

Local audio or video transcription is not supported yet. For such files, provide a subtitle file.

## Feedback

Open an [issue](https://github.com/veardk/textcast/issues) for bugs or ideas. Problems with the reading window itself belong in [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi/issues).

## License

[MIT](LICENSE)
