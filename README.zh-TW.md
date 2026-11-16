<div align="center">
  <img src="assets/icon.png" alt="Textcast" width="120">
  <h1>Textcast</h1>
  <p><strong>把 Podcast 和影片變成可以讀的文字，邊讀邊和你的 agent 對話。</strong></p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/veardk/textcast?style=flat-square" alt="License"></a>
    <a href="https://github.com/veardk/textcast/releases"><img src="https://img.shields.io/github/v/release/veardk/textcast?style=flat-square" alt="Release"></a>
    <a href="https://github.com/veardk/textcast/stargazers"><img src="https://img.shields.io/github/stars/veardk/textcast?style=flat-square" alt="Stars"></a>
    <a href="#安裝"><img src="https://img.shields.io/badge/Agent-Skill-1B365D?style=flat-square" alt="Agent Skill"></a>
  </p>
  <p><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <strong>繁體中文</strong> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a></p>
</div>

Textcast 把一集 Podcast 或一部影片變成真正能讀的文字：完整的逐字稿，翻譯成你的語言，依主題整理並附上解讀，全部放在一個閱讀頁面裡。你可以照自己的節奏閱讀，不必在一小時的音訊裡來回拖曳進度條。

頁面是「活」的。它會在閱讀視窗中開啟，你的 agent 就在旁邊：選取任何一句話就能提問，或請它修改，agent 會回答並在你閱讀時直接更新頁面。點擊任何一行，影片會在小視窗裡從那一刻開始播放，隨時能聽到原話是怎麼說的。

長篇文章和文件也同樣適用。Textcast 是一個 Agent Skill：由你的 agent 親自閱讀和翻譯，腳本負責字幕、時間軸和檢查，所以沒有一句話會被概括掉。

## 安裝

每個 agent 選一種方式即可。同一個 Skill 裝兩次（例如同時裝外掛又用 `npx skills` 安裝），agent 會看到兩份。

### 任何 agent（推薦）

```bash
npx skills@latest add veardk/textcast -g
```

`-g` 表示為目前使用者安裝，在任何資料夾都能用。加上 `-a <agent>` 可以直接指定 agent（`claude-code`、`codex`、`cursor`、`opencode`、`windsurf` 等），不加則從清單中選擇。更新請執行 `npx skills@latest update textcast`。

<details>
<summary><strong>Claude Code</strong>（外掛）</summary>

```bash
claude plugin marketplace add veardk/textcast
claude plugin install textcast@veardk
```

更新時先執行 `claude plugin marketplace update veardk`，再執行 `claude plugin update textcast@veardk`。

</details>

<details>
<summary><strong>Codex</strong>（外掛）</summary>

```bash
codex plugin marketplace add veardk/textcast
codex plugin add textcast@veardk
```

啟動時自動更新。

</details>

<details>
<summary><strong>GitHub Copilot</strong>（CLI 和 VS Code）</summary>

```bash
copilot plugin marketplace add veardk/textcast
copilot plugin install textcast@veardk
```

在 VS Code 中執行 **Chat: Install Plugin From Source**，輸入 `https://github.com/veardk/textcast`。

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/veardk/textcast.git --path skills/textcast
```

再執行一次即可更新。

</details>

<details>
<summary><strong>手動安裝</strong>（git clone）</summary>

複製儲存庫，再把其中的 Skill 資料夾拷貝到 agent 的 skills 資料夾。以 Claude Code 為例：

```bash
git clone https://github.com/veardk/textcast.git
cp -R textcast/skills/textcast ~/.claude/skills/
```

更新時重新拉取並拷貝一次。

</details>

## 使用

對你的 agent 說，例如：

> /textcast https://www.youtube.com/watch?v=…

> 把 https://www.youtube.com/watch?v=… 做成繁體中文的 Textcast 頁面。

agent 會取得內容、翻譯、依主題整理、發布頁面，然後在閱讀視窗中開啟，你可以針對任何一句話提問。

## 功能

- **用讀的取代用看的**：YouTube 或 Bilibili 上 Podcast、影片的完整逐字稿，每一行依序呈現，一句不漏。
- **你的語言**：原文、譯文或左右雙語對照閱讀，由你的 agent 翻譯。
- **邊讀邊聊**：頁面在閱讀視窗（[textcast-chat-axi](https://github.com/veardk/textcast-chat-axi)）中開啟，旁邊是即時對話面板。選取任何文字即可向 agent 提問或要求修改，頁面會就地更新。
- **小視窗影片播放**：點擊任何一行，影片就在正文旁的小視窗裡從那一刻開始播放，可以邊聽邊繼續讀。
- **主題與解讀**：逐字稿依主題分成卡片，每張都有 agent 的講解，還可以產生一頁摘要。
- **可信的時間戳記**：每個時間都來自字幕，從不猜測。
- **也支援任何長篇文字**：字幕檔（`.srt`、`.vtt`、`.json`）、Markdown 或純文字，以及從 PDF 或網頁擷取的文字。
- **你自己的文庫**：頁面依分類整理，附一個首頁；支援淺色、深色、護眼三種主題，介面文字支援 17 種語言。

## 頁面存在哪裡

頁面存在你執行 agent 的那個資料夾下的 `./textcast/output/`，而不是 skill 資料夾裡：

```text
textcast/output/
├── index.html                      # 文庫首頁
├── <category>/NN-<slug>.html       # 逐字稿頁面
├── <category>/NN-<slug>-summary.html
└── .work/                          # 中間檔案（字幕、譯文）
```

每個頁面都是一個獨立的 HTML 檔案，直接開啟也能用。

## 環境需求

- Python 3.10 或更新版本（只用標準函式庫）
- Node.js 22 或更新版本，用於取得字幕和閱讀視窗（第一次使用時由 `npx` 自動下載）
- `yt-dlp`（選用），YouTube 字幕取得失敗時自動使用
- Bilibili 字幕需要登入。腳本會從瀏覽器讀取 cookie，或提供掃碼登入，cookie 存放在 `~/.textcast/`。

暫不支援本機音訊或影片轉寫。這類檔案請提供字幕檔。

## 回饋

有 bug 或想法，歡迎提交 [issue](https://github.com/veardk/textcast/issues)。閱讀視窗本身的問題請提到 [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi/issues)。

## 致謝

頁面設計和配色參考了 [Kami](https://github.com/tw93/Kami)。

## 授權

[MIT](LICENSE)
