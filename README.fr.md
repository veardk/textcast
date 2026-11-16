<div align="center">
  <img src="assets/icon.png" alt="Textcast" width="120">
  <h1>Textcast</h1>
  <p><strong>Lisez les podcasts et les vidéos au lieu de les regarder, et parlez à votre agent pendant votre lecture.</strong></p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/veardk/textcast?style=flat-square" alt="License"></a>
    <a href="https://github.com/veardk/textcast/releases"><img src="https://img.shields.io/github/v/release/veardk/textcast?style=flat-square" alt="Release"></a>
    <a href="https://github.com/veardk/textcast/stargazers"><img src="https://img.shields.io/github/stars/veardk/textcast?style=flat-square" alt="Stars"></a>
    <a href="#installation"><img src="https://img.shields.io/badge/Agent-Skill-1B365D?style=flat-square" alt="Agent Skill"></a>
  </p>
  <p><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.zh-TW.md">繁體中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.es.md">Español</a> · <strong>Français</strong> · <a href="README.de.md">Deutsch</a></p>
</div>

Textcast transforme un podcast ou une vidéo en un texte que l'on peut vraiment lire : la transcription complète, traduite dans votre langue, organisée par thèmes avec une analyse, dans une seule page de lecture. Vous lisez à votre rythme au lieu de naviguer dans une heure d'audio.

La page est vivante. Elle s'ouvre dans une fenêtre de lecture, votre agent juste à côté : sélectionnez n'importe quelle phrase pour poser une question ou demander une modification, et l'agent répond et met la page à jour pendant que vous lisez. Cliquez sur n'importe quelle ligne et la vidéo démarre à ce moment-là dans un petit lecteur flottant, pour toujours entendre comment cela a été dit.

Cela fonctionne aussi pour les longs articles et documents. Textcast est une Agent Skill : votre agent lit et traduit lui-même, et les scripts s'occupent des sous-titres, du minutage et des vérifications, si bien qu'aucune ligne n'est perdue dans un résumé.

## Installation

Choisissez une seule méthode par agent. Installer la même Skill deux fois (par exemple en plugin et avec `npx skills`) en donne deux copies à votre agent.

### N'importe quel agent (recommandé)

```bash
npx skills@latest add veardk/textcast -g
```

`-g` l'installe pour votre utilisateur, elle fonctionne donc dans tous les dossiers. Ajoutez `-a <agent>` pour choisir l'agent d'emblée (`claude-code`, `codex`, `cursor`, `opencode`, `windsurf`, …), ou omettez-le et choisissez dans la liste. Pour mettre à jour, lancez `npx skills@latest update textcast`.

<details>
<summary><strong>Claude Code</strong> (plugin)</summary>

```bash
claude plugin marketplace add veardk/textcast
claude plugin install textcast@veardk
```

Pour mettre à jour, lancez `claude plugin marketplace update veardk`, puis `claude plugin update textcast@veardk`.

</details>

<details>
<summary><strong>Codex</strong> (plugin)</summary>

```bash
codex plugin marketplace add veardk/textcast
codex plugin add textcast@veardk
```

Se met à jour automatiquement au démarrage.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI et VS Code)</summary>

```bash
copilot plugin marketplace add veardk/textcast
copilot plugin install textcast@veardk
```

Dans VS Code, lancez **Chat: Install Plugin From Source** et saisissez `https://github.com/veardk/textcast`.

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/veardk/textcast.git --path skills/textcast
```

Relancez-la pour mettre à jour.

</details>

<details>
<summary><strong>Manuelle</strong> (git clone)</summary>

Clonez le dépôt, puis copiez le dossier de la Skill dans le dossier de skills de votre agent. Pour Claude Code :

```bash
git clone https://github.com/veardk/textcast.git
cp -R textcast/skills/textcast ~/.claude/skills/
```

Pour mettre à jour, refaites un pull et copiez-le à nouveau.

</details>

## Utilisation

Demandez à votre agent, par exemple :

> /textcast https://www.youtube.com/watch?v=…

> Transforme https://www.youtube.com/watch?v=… en page Textcast en français.

L'agent récupère le contenu, le traduit, le regroupe par thèmes, publie la page et l'ouvre dans une fenêtre de lecture où vous pouvez poser une question sur n'importe quelle phrase.

## Fonctionnalités

- **Lire au lieu de regarder** : la transcription complète d'un podcast ou d'une vidéo YouTube ou Bilibili, chaque ligne dans l'ordre, rien d'omis.
- **Dans votre langue** : lecture en original, en traduction ou bilingue côte à côte, traduite par votre agent.
- **Parler en lisant** : la page s'ouvre dans une fenêtre de lecture ([textcast-chat-axi](https://github.com/veardk/textcast-chat-axi)) avec un panneau de conversation en direct. Sélectionnez un texte pour interroger votre agent ou demander une modification, et la page se met à jour sur place.
- **Lecteur vidéo flottant** : cliquez sur n'importe quelle ligne et la vidéo démarre à ce moment-là dans une petite fenêtre à côté du texte, pour écouter tout en continuant à lire.
- **Thèmes et analyse** : la transcription est regroupée en cartes thématiques, chacune avec l'explication de l'agent, plus une page de résumé facultative.
- **Des horodatages fiables** : chaque temps vient des sous-titres, jamais deviné.
- **Aussi pour tout long texte** : fichiers de sous-titres (`.srt`, `.vtt`, `.json`), Markdown ou texte, ou le texte d'un PDF ou d'une page web.
- **Votre propre bibliothèque** : les pages sont classées par catégories avec une page d'index, en thème clair, sombre ou sépia, avec une interface en 17 langues.

## Où vont les pages

Les pages sont écrites dans `./textcast/output/`, dans le dossier où vous lancez votre agent, et non dans le dossier de la skill :

```text
textcast/output/
├── index.html                      # la bibliothèque
├── <category>/NN-<slug>.html       # page de transcription
├── <category>/NN-<slug>-summary.html
└── .work/                          # fichiers intermédiaires (sous-titres, traductions)
```

Chaque page est un fichier HTML unique qui fonctionne aussi quand on l'ouvre directement.

## Prérequis

- Python 3.10 ou plus récent (bibliothèque standard uniquement)
- Node.js 22 ou plus récent, pour récupérer les sous-titres et pour la fenêtre de lecture (`npx` la télécharge à la première utilisation)
- `yt-dlp` (facultatif), utilisé automatiquement quand la récupération des sous-titres YouTube échoue
- Les sous-titres Bilibili nécessitent une session connectée. Le script lit le cookie de votre navigateur ou propose une connexion par QR code, et l'enregistre dans `~/.textcast/`.

La transcription locale d'audio ou de vidéo n'est pas encore prise en charge. Pour ces fichiers, fournissez un fichier de sous-titres.

## Retours

Ouvrez une [issue](https://github.com/veardk/textcast/issues) pour les bugs ou les idées. Les problèmes de la fenêtre de lecture elle-même vont dans [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi/issues).

## Remerciements

Le design et les couleurs de la page s'inspirent de [Kami](https://github.com/tw93/Kami).

## Licence

[MIT](LICENSE)
