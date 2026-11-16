<div align="center">
  <img src="assets/icon.png" alt="Textcast" width="120">
  <h1>Textcast</h1>
  <p>Podcasts und Videos lesen statt ansehen – und beim Lesen mit deinem Agenten sprechen.</p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/veardk/textcast?style=flat-square" alt="License"></a>
    <a href="https://github.com/veardk/textcast/releases"><img src="https://img.shields.io/github/v/release/veardk/textcast?style=flat-square" alt="Release"></a>
    <a href="https://github.com/veardk/textcast/stargazers"><img src="https://img.shields.io/github/stars/veardk/textcast?style=flat-square" alt="Stars"></a>
    <a href="#installation"><img src="https://img.shields.io/badge/Agent-Skill-1B365D?style=flat-square" alt="Agent Skill"></a>
  </p>
  <p><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.zh-TW.md">繁體中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <strong>Deutsch</strong></p>
</div>

Textcast macht aus einem Podcast oder Video einen Text, den man wirklich lesen kann: das vollständige Transkript, in deine Sprache übersetzt, nach Themen gegliedert und mit Analyse, auf einer einzigen Leseseite. Du liest in deinem eigenen Tempo, statt dich durch eine Stunde Audio zu spulen.

Die Seite ist lebendig. Sie öffnet sich in einem Lesefenster, dein Agent direkt daneben: Markiere einen beliebigen Satz, um danach zu fragen oder eine Änderung zu wünschen, und der Agent antwortet und aktualisiert die Seite, während du liest. Klicke auf eine beliebige Zeile, und das Video spielt ab genau diesem Moment in einem kleinen schwebenden Player – so hörst du jederzeit, wie es gesagt wurde.

Auch lange Artikel und Dokumente funktionieren. Textcast ist ein Agent Skill: Dein Agent liest und übersetzt selbst, die Skripte kümmern sich um Untertitel, Zeiten und Prüfungen, sodass keine Zeile in einer Zusammenfassung verloren geht.

## Installation

Wähle pro Agent nur einen Weg. Wer denselben Skill zweimal installiert (etwa als Plugin und mit `npx skills`), gibt seinem Agenten zwei Kopien.

### Jeder Agent (empfohlen)

```bash
npx skills@latest add veardk/textcast -g
```

`-g` installiert ihn für deinen Benutzer, er funktioniert also in jedem Ordner. Mit `-a <agent>` legst du den Agenten direkt fest (`claude-code`, `codex`, `cursor`, `opencode`, `windsurf`, …), ohne die Option wählst du aus einer Liste. Zum Aktualisieren `npx skills@latest update textcast` ausführen.

<details>
<summary><strong>Claude Code</strong> (Plugin)</summary>

```bash
claude plugin marketplace add veardk/textcast
claude plugin install textcast@veardk
```

Zum Aktualisieren `claude plugin marketplace update veardk` und danach `claude plugin update textcast@veardk` ausführen.

</details>

<details>
<summary><strong>Codex</strong> (Plugin)</summary>

```bash
codex plugin marketplace add veardk/textcast
codex plugin add textcast@veardk
```

Aktualisiert sich beim Start von selbst.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI und VS Code)</summary>

```bash
copilot plugin marketplace add veardk/textcast
copilot plugin install textcast@veardk
```

In VS Code **Chat: Install Plugin From Source** ausführen und `https://github.com/veardk/textcast` eingeben.

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/veardk/textcast.git
```

Zum Aktualisieren erneut ausführen.

</details>

<details>
<summary><strong>Manuell</strong> (git clone)</summary>

Klone das Repository in den Skills-Ordner deines Agenten. Für Claude Code:

```bash
git clone https://github.com/veardk/textcast.git ~/.claude/skills/textcast
```

Zum Aktualisieren in diesem Ordner `git pull` ausführen.

</details>

## Verwendung

Bitte deinen Agenten zum Beispiel:

> /textcast https://www.youtube.com/watch?v=…

> Mach aus https://www.youtube.com/watch?v=… eine Textcast-Seite auf Deutsch.

Der Agent holt den Inhalt, übersetzt ihn, gliedert ihn nach Themen, veröffentlicht die Seite und öffnet sie in einem Lesefenster, in dem du zu jedem Satz Fragen stellen kannst.

## Funktionen

- **Lesen statt ansehen**: das vollständige Transkript eines Podcasts oder Videos von YouTube oder Bilibili, jede Zeile in Reihenfolge, nichts ausgelassen.
- **In deiner Sprache**: Original, Übersetzung oder zweisprachig nebeneinander, übersetzt von deinem Agenten.
- **Beim Lesen sprechen**: Die Seite öffnet sich in einem Lesefenster ([textcast-chat-axi](https://github.com/veardk/textcast-chat-axi)) mit einem Live-Gesprächsbereich. Markiere einen Text, um deinen Agenten zu fragen oder eine Änderung zu wünschen, und die Seite aktualisiert sich direkt.
- **Schwebender Videoplayer**: Klicke auf eine beliebige Zeile, und das Video spielt ab diesem Moment in einem kleinen Fenster neben dem Text – zuhören und weiterlesen.
- **Themen und Analyse**: Das Transkript wird in Themenkarten gegliedert, jede mit einer Erklärung des Agenten, dazu eine optionale Zusammenfassungsseite.
- **Verlässliche Zeitstempel**: Jede Zeit stammt aus den Untertiteln, nie geraten.
- **Auch für jeden langen Text**: Untertiteldateien (`.srt`, `.vtt`, `.json`), Markdown oder Text sowie Text aus einem PDF oder einer Webseite.
- **Deine eigene Bibliothek**: Seiten werden in Kategorien mit einer Indexseite geordnet, im hellen, dunklen oder Sepia-Design, mit Oberfläche in 17 Sprachen.

## Wo die Seiten landen

Die Seiten werden nach `./textcast/output/` in dem Ordner geschrieben, in dem du deinen Agenten startest, nicht in den Skill-Ordner:

```text
textcast/output/
├── index.html                      # die Bibliothek
├── <category>/NN-<slug>.html       # Transkriptseite
├── <category>/NN-<slug>-summary.html
└── .work/                          # Zwischendateien (Untertitel, Übersetzungen)
```

Jede Seite ist eine einzelne HTML-Datei, die auch direkt geöffnet funktioniert.

## Voraussetzungen

- Python 3.10 oder neuer (nur Standardbibliothek)
- Node.js 22 oder neuer, für das Abrufen der Untertitel und das Lesefenster (`npx` lädt es beim ersten Mal herunter)
- `yt-dlp` (optional), wird automatisch genutzt, wenn das Abrufen der YouTube-Untertitel scheitert
- Bilibili-Untertitel brauchen eine angemeldete Sitzung. Das Skript liest das Cookie aus deinem Browser oder bietet eine QR-Anmeldung an und speichert es in `~/.textcast/`.

Lokale Transkription von Audio oder Video wird noch nicht unterstützt. Für solche Dateien bitte eine Untertiteldatei bereitstellen.

## Feedback

Öffne ein [Issue](https://github.com/veardk/textcast/issues) für Fehler oder Ideen. Probleme mit dem Lesefenster selbst gehören zu [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi/issues).

## Danksagung

Design und Farben der Seite sind von [Kami](https://github.com/tw93/Kami) inspiriert.

## Lizenz

[MIT](LICENSE)
