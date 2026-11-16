<div align="center">
  <img src="assets/icon.png" alt="Textcast" width="120">
  <h1>Textcast</h1>
  <p>Lee pódcasts y vídeos en lugar de verlos, y habla con tu agente mientras lees.</p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/veardk/textcast?style=flat-square" alt="License"></a>
    <a href="https://github.com/veardk/textcast/releases"><img src="https://img.shields.io/github/v/release/veardk/textcast?style=flat-square" alt="Release"></a>
    <a href="https://github.com/veardk/textcast/stargazers"><img src="https://img.shields.io/github/stars/veardk/textcast?style=flat-square" alt="Stars"></a>
    <a href="#instalación"><img src="https://img.shields.io/badge/Agent-Skill-1B365D?style=flat-square" alt="Agent Skill"></a>
  </p>
  <p><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.zh-TW.md">繁體中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <strong>Español</strong> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a></p>
</div>

Textcast convierte un pódcast o un vídeo en un texto que de verdad puedes leer: la transcripción completa, traducida a tu idioma, organizada por temas con análisis, en una sola página de lectura. Lees a tu ritmo en lugar de ir y venir por una hora de audio.

La página está viva. Se abre en una ventana de lectura con tu agente al lado: selecciona cualquier frase para preguntar por ella o pedir un cambio, y el agente responde y actualiza la página mientras lees. Haz clic en cualquier línea y el vídeo se reproduce desde ese momento en un pequeño reproductor flotante, para que siempre puedas oír cómo se dijo.

También sirve para artículos y documentos largos. Textcast es una Agent Skill: tu agente lee y traduce por sí mismo, y los scripts se encargan de los subtítulos, los tiempos y las comprobaciones, así que ninguna línea se pierde en un resumen.

## Instalación

Elige una sola vía por agente. Si instalas la misma Skill dos veces (por ejemplo, como plugin y con `npx skills`), tu agente verá dos copias.

### Cualquier agente (recomendado)

```bash
npx skills@latest add veardk/textcast -g
```

`-g` la instala para tu usuario, así funciona en cualquier carpeta. Añade `-a <agent>` para elegir el agente de antemano (`claude-code`, `codex`, `cursor`, `opencode`, `windsurf`, …), o déjalo fuera y elige de la lista. Para actualizar, ejecuta `npx skills@latest update textcast`.

<details>
<summary><strong>Claude Code</strong> (plugin)</summary>

```bash
claude plugin marketplace add veardk/textcast
claude plugin install textcast@veardk
```

Para actualizar, ejecuta `claude plugin marketplace update veardk` y después `claude plugin update textcast@veardk`.

</details>

<details>
<summary><strong>Codex</strong> (plugin)</summary>

```bash
codex plugin marketplace add veardk/textcast
codex plugin add textcast@veardk
```

Se actualiza solo al iniciar.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI y VS Code)</summary>

```bash
copilot plugin marketplace add veardk/textcast
copilot plugin install textcast@veardk
```

En VS Code, ejecuta **Chat: Install Plugin From Source** e introduce `https://github.com/veardk/textcast`.

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/veardk/textcast.git
```

Vuelve a ejecutarlo para actualizar.

</details>

<details>
<summary><strong>Manual</strong> (git clone)</summary>

Clona el repositorio en la carpeta de skills de tu agente. Para Claude Code:

```bash
git clone https://github.com/veardk/textcast.git ~/.claude/skills/textcast
```

Para actualizar, ejecuta `git pull` en esa carpeta.

</details>

## Uso

Pídeselo a tu agente, por ejemplo:

> /textcast https://www.youtube.com/watch?v=…

> Convierte https://www.youtube.com/watch?v=… en una página de Textcast en español.

El agente obtiene el contenido, lo traduce, lo agrupa por temas, publica la página y la abre en una ventana de lectura donde puedes preguntar por cualquier frase.

## Funciones

- **Leer en lugar de ver**: la transcripción completa de un pódcast o vídeo de YouTube o Bilibili, cada línea en orden, sin omitir nada.
- **En tu idioma**: lectura en original, traducción o bilingüe lado a lado, traducida por tu agente.
- **Habla mientras lees**: la página se abre en una ventana de lectura ([textcast-chat-axi](https://github.com/veardk/textcast-chat-axi)) con un panel de conversación en tiempo real. Selecciona cualquier texto para preguntar a tu agente o pedir un cambio, y la página se actualiza al instante.
- **Reproductor de vídeo flotante**: haz clic en cualquier línea y el vídeo se reproduce desde ese momento en una pequeña ventana junto al texto, para escuchar y seguir leyendo.
- **Temas y análisis**: la transcripción se agrupa en tarjetas por tema, cada una con la explicación del agente, y una página de resumen opcional.
- **Marcas de tiempo fiables**: todos los tiempos salen de los subtítulos, nunca se inventan.
- **También cualquier texto largo**: archivos de subtítulos (`.srt`, `.vtt`, `.json`), Markdown o texto, o el texto de un PDF o una página web.
- **Tu propia biblioteca**: las páginas se agrupan en categorías con una página índice, en tema claro, oscuro o sepia, con la interfaz en 17 idiomas.

## Dónde se guardan las páginas

Las páginas se escriben en `./textcast/output/` dentro de la carpeta donde ejecutas tu agente, no en la carpeta de la skill:

```text
textcast/output/
├── index.html                      # la biblioteca
├── <category>/NN-<slug>.html       # página de transcripción
├── <category>/NN-<slug>-summary.html
└── .work/                          # archivos intermedios (subtítulos, traducciones)
```

Cada página es un único archivo HTML que también funciona si lo abres directamente.

## Requisitos

- Python 3.10 o posterior (solo la biblioteca estándar)
- Node.js 22 o posterior, para obtener los subtítulos y para la ventana de lectura (`npx` la descarga la primera vez)
- `yt-dlp` (opcional), se usa automáticamente cuando falla la descarga de subtítulos de YouTube
- Los subtítulos de Bilibili requieren una sesión iniciada. El script lee la cookie de tu navegador u ofrece un inicio de sesión con QR, y la guarda en `~/.textcast/`.

La transcripción de audio o vídeo local todavía no está disponible. Para esos archivos, aporta un archivo de subtítulos.

## Comentarios

Abre un [issue](https://github.com/veardk/textcast/issues) para errores o ideas. Los problemas de la ventana de lectura van en [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi/issues).

## Agradecimientos

El diseño y los colores de la página se inspiran en [Kami](https://github.com/tw93/Kami).

## Licencia

[MIT](LICENSE)
