#!/usr/bin/env node
/**
 * YouTube Transcript Extractor (Zero-Dependency Node.js Edition)
 * 
 * Features:
 *  - Native Innertube ANDROID client protocol (bypasses WEB PO Token / 429 rate limit)
 *  - Multi-language fallback: prioritized by user input -> 'en' -> i18n ranking -> first available
 *  - Output formats: srt, vtt, txt, md, json
 * 
 * Usage:
 *  node base-youtube-transcript.mjs <VideoURL_or_ID> [options]
 * 
 * Options:
 *  -f, --format <srt|vtt|txt|md|json>  Output format (default: srt)
 *  -o, --output <file_path>             Custom output file path
 *  -l, --lang <lang_code>               Specified language (e.g., en, zh-Hans)
 *  --stdout                             Print to console without saving to disk
 *  -h, --help                           Show help message
 */

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36";
const YT_HOSTS = new Set(["www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"]);
const XML_ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
const CJK = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}　-〿＀-￯]/u;

// Standard i18n priority fallback chain (English first, followed by major world languages)
const I18N_FALLBACK_ORDER = [
  "en", "en-US", "en-GB",
  "zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW",
  "es", "ja", "ko", "fr", "de", "ru", "pt", "it", "ar", "hi"
];

// Extract 11-char Video ID
function extractVideoId(input) {
  const text = String(input || "").trim();
  const idPattern = /^[A-Za-z0-9_-]{11}$/;
  if (idPattern.test(text)) return text;
  try {
    const parsed = new URL(text.startsWith("http") ? text : `https://${text}`);
    if (parsed.hostname === "youtu.be") {
      const id = parsed.pathname.slice(1).split("/")[0];
      return idPattern.test(id) ? id : "";
    }
    if (YT_HOSTS.has(parsed.hostname)) {
      const fromQuery = parsed.searchParams.get("v");
      if (fromQuery && idPattern.test(fromQuery)) return fromQuery;
      const fromPath = parsed.pathname.match(/^\/(?:shorts|embed|live|v)\/([A-Za-z0-9_-]{11})/)?.[1];
      if (fromPath && idPattern.test(fromPath)) return fromPath;
    }
  } catch {}
  const match = text.match(/(?:v=|\/shorts\/|\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return match ? match[1] : "";
}

// Decode XML entities
function decodeXmlEntities(text) {
  return String(text).replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (whole, body) => {
    if (body[0] === "#") {
      const code = body[1] === "x" || body[1] === "X" ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      return Number.isFinite(code) && code <= 0x10ffff ? String.fromCodePoint(code) : whole;
    }
    return XML_ENTITIES[body.toLowerCase()] ?? whole;
  });
}

// Format CJK spacing & line breaks
function joinCaptionLines(text) {
  return String(text)
    .replace(/\s*\n\s*/g, (match, offset, whole) =>
      CJK.test(whole[offset - 1] || "") && CJK.test(whole[offset + match.length] || "") ? "" : " "
    )
    .replace(/\s+/g, " ");
}

// Parse Timedtext XML (srv3)
function parseSrv3Xml(xml) {
  const items = [];
  const regex = /<p\b([^>]*)>([\s\S]*?)<\/p>/g;
  let match;
  while ((match = regex.exec(String(xml))) !== null) {
    const attrs = match[1];
    const fromMatch = attrs.match(/\bt="([^"]*)"/);
    const durMatch = attrs.match(/\bd="([^"]*)"/);
    const from = Number(fromMatch?.[1]);
    const duration = Number(durMatch?.[1]) || 0;
    const content = joinCaptionLines(
      decodeXmlEntities(match[2].replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, ""))
    ).trim();
    if (!Number.isFinite(from) || !content) continue;
    items.push({
      start: from / 1000,
      end: (from + duration) / 1000,
      text: content
    });
  }
  return items;
}

// Parse JSON3 format
function parseJson3(data) {
  const events = Array.isArray(data?.events) ? data.events : [];
  return events
    .filter((event) => Number.isFinite(event?.tStartMs) && Array.isArray(event.segs) && !event.aAppend)
    .map((event) => {
      const start = event.tStartMs / 1000;
      const duration = (Number(event.dDurationMs) || 0) / 1000;
      const text = joinCaptionLines(event.segs.map((seg) => String(seg?.utf8 || "")).join("")).trim();
      return { start, end: start + duration, text };
    })
    .filter((seg) => seg.text);
}

// Select track based on language priority: User input -> English -> i18n list -> First available
function pickTrackByPriority(tracks, preferredLang = "") {
  if (!tracks.length) return null;
  // Textcast patch: human-made tracks outrank auto-generated (asr) ones for the same language
  tracks = [...tracks].sort((a, b) => (a.kind === "asr") - (b.kind === "asr"));

  // 1. User explicitly specified language
  if (preferredLang) {
    const target = preferredLang.toLowerCase();
    const userMatch = tracks.find((t) => t.languageCode?.toLowerCase() === target || t.languageCode?.toLowerCase().startsWith(target));
    if (userMatch) return userMatch;
  }

  // 2. Iterate through i18n order (en is #1)
  for (const lang of I18N_FALLBACK_ORDER) {
    const target = lang.toLowerCase();
    const match = tracks.find((t) => {
      const code = (t.languageCode || "").toLowerCase();
      return code === target || code.startsWith(`${target}-`) || (target.length === 2 && code.startsWith(target));
    });
    if (match) return match;
  }

  // 3. Fallback to whatever language is available
  return tracks[0];
}

async function fetchYoutubeTranscript(videoId, { preferredLang = "" } = {}) {
  const apiUrl = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false";
  const body = {
    context: {
      client: {
        clientName: "ANDROID",
        clientVersion: "21.26.364",
        androidSdkVersion: 30,
        osName: "Android",
        osVersion: "11",
        hl: "en"
      }
    },
    videoId
  };

  const res = await fetch(apiUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "User-Agent": "com.google.android.youtube/21.26.364 (Linux; U; Android 11)"
    },
    body: JSON.stringify(body)
  });

  const data = await res.json();
  const title = data.videoDetails?.title || `YouTube_${videoId}`;
  const renderer = data.captions?.playerCaptionsTracklistRenderer;
  const tracks = renderer?.captionTracks || [];

  if (!tracks.length) {
    throw { message: "No caption tracks available for this video (possibly music, muted, or copyright restricted).", title };
  }

  const selectedTrack = pickTrackByPriority(tracks, preferredLang);
  const subRes = await fetch(selectedTrack.baseUrl, {
    headers: { "User-Agent": USER_AGENT }
  });

  if (!subRes.ok) {
    throw { message: `Timedtext request failed with HTTP ${subRes.status}`, title };
  }

  const rawText = await subRes.text();
  let segments = [];
  if (rawText.trim().startsWith("{")) {
    segments = parseJson3(JSON.parse(rawText));
  } else {
    segments = parseSrv3Xml(rawText);
  }

  if (!segments.length) {
    throw { message: "Subtitle file was fetched but contained empty segments.", title };
  }

  const langLabel = selectedTrack.name?.runs?.[0]?.text
    ? `${selectedTrack.languageCode} (${selectedTrack.name.runs[0].text})`
    : selectedTrack.languageCode;

  return {
    platform: "youtube",
    videoId,
    title,
    language: langLabel,
    langCode: selectedTrack.languageCode,
    isAutoGenerated: selectedTrack.kind === "asr",
    segments
  };
}

// Timestamp formatters
function formatTimeSrt(sec) {
  const ms = Math.floor((sec % 1) * 1000);
  const totalSec = Math.floor(sec);
  const s = totalSec % 60;
  const m = Math.floor(totalSec / 60) % 60;
  const h = Math.floor(totalSec / 3600);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms).padStart(3, "0")}`;
}

function formatTimeVtt(sec) {
  return formatTimeSrt(sec).replace(",", ".");
}

function formatTimeTag(sec) {
  const totalSec = Math.floor(sec);
  const s = totalSec % 60;
  const m = Math.floor(totalSec / 60) % 60;
  const h = Math.floor(totalSec / 3600);
  return h > 0
    ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function renderOutput(data, format = "srt") {
  const { segments } = data;
  switch (format.toLowerCase()) {
    case "srt":
      return segments
        .map((seg, i) => `${i + 1}\n${formatTimeSrt(seg.start)} --> ${formatTimeSrt(seg.end)}\n${seg.text}\n`)
        .join("\n");
    case "vtt":
      return `WEBVTT\n\n` + segments
        .map((seg, i) => `${i + 1}\n${formatTimeVtt(seg.start)} --> ${formatTimeVtt(seg.end)}\n${seg.text}\n`)
        .join("\n");
    case "txt":
      return segments.map((seg) => seg.text).join("\n");
    case "md":
      return `# ${data.title}\n\n` +
        `> Source: YouTube (${data.videoId}) | Language: ${data.language} | Segments: ${segments.length}\n\n` +
        segments.map((seg) => `\`[${formatTimeTag(seg.start)}]\` ${seg.text}`).join("\n\n");
    case "json":
      return JSON.stringify(data, null, 2);
    default:
      throw new Error(`Unsupported format: ${format}`);
  }
}

function sanitizeFilename(name) {
  return name.replace(/[\\/:*?"<>|]/g, "_").slice(0, 100);
}

function parseCliArgs() {
  const args = process.argv.slice(2);
  const options = {
    input: "",
    format: "srt",
    output: "",
    lang: "",
    stdout: false
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-f" || arg === "--format") {
      options.format = args[++i];
    } else if (arg === "-o" || arg === "--output") {
      options.output = args[++i];
    } else if (arg === "-l" || arg === "--lang") {
      options.lang = args[++i];
    } else if (arg === "--stdout") {
      options.stdout = true;
    } else if (arg === "-h" || arg === "--help") {
      printHelp();
      process.exit(0);
    } else if (!arg.startsWith("-") && !options.input) {
      options.input = arg;
    }
  }

  return options;
}

function printHelp() {
  console.log(`
YouTube Transcript Extractor (Zero-Dependency Node.js)

Usage:
  node base-youtube-transcript.mjs <VideoURL_or_ID> [options]

Examples:
  node base-youtube-transcript.mjs dQw4w9WgXcQ
  node base-youtube-transcript.mjs "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  node base-youtube-transcript.mjs dQw4w9WgXcQ -f md -o rick.md
  node base-youtube-transcript.mjs dQw4w9WgXcQ -f json --stdout

Options:
  -f, --format <srt|vtt|txt|md|json>  Output format (default: srt)
  -o, --output <path>                  Custom output file path
  -l, --lang <lang_code>               Preferred language code (e.g. en, zh-Hans)
  --stdout                             Output to stdout directly without saving
  -h, --help                           Show this help message
`);
}

async function main() {
  const options = parseCliArgs();

  if (!options.input) {
    printHelp();
    process.exit(1);
  }

  const videoId = extractVideoId(options.input);
  if (!videoId) {
    console.error("Error: Invalid YouTube Video ID or URL.");
    process.exit(1);
  }

  const startTime = Date.now();
  console.log(`[*] Processing YouTube Video: ${videoId}...`);

  try {
    const result = await fetchYoutubeTranscript(videoId, { preferredLang: options.lang });
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(2);
    const elapsedTime = `${elapsedSec}s`;

    // Standardized English response summary
    console.log("--------------------------------------------------");
    console.log(`Status: SUCCESS`);
    console.log(`Title: ${result.title}`);
    console.log(`Language: ${result.language}${result.isAutoGenerated ? " (Auto-Generated)" : ""}`);
    console.log(`Elapsed Time: ${elapsedTime}`);
    console.log(`Segments: ${result.segments.length}`);
    console.log("--------------------------------------------------");

    const payload = {
      status: "SUCCESS",
      platform: "youtube",
      videoId,
      title: result.title,
      language: result.language,
      elapsedTime,
      segmentCount: result.segments.length,
      segments: result.segments
    };

    if (options.format.toLowerCase() === "json" && options.stdout) {
      console.log(JSON.stringify(payload, null, 2));
      return;
    }

    const content = renderOutput(result, options.format);

    if (options.stdout) {
      console.log("\n" + content);
      return;
    }

    const ext = options.format.toLowerCase();
    const defaultFilename = `[YouTube]_${sanitizeFilename(result.title)}.${ext}`;
    const outPath = options.output ? path.resolve(options.output) : path.resolve(process.cwd(), defaultFilename);

    await fs.writeFile(outPath, content, "utf-8");
    console.log(`Saved To: ${outPath}`);
    console.log(`\nPreview (First 3 Segments):`);
    result.segments.slice(0, 3).forEach((s) => {
      console.log(`  [${formatTimeTag(s.start)} -> ${formatTimeTag(s.end)}] ${s.text}`);
    });
  } catch (err) {
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(2);
    const elapsedTime = `${elapsedSec}s`;
    const errorMsg = err.message || String(err);
    const title = err.title || "Unknown";

    console.log("--------------------------------------------------");
    console.log(`Status: FAILED`);
    console.log(`Title: ${title}`);
    console.log(`Language: N/A`);
    console.log(`Elapsed Time: ${elapsedTime}`);
    console.log(`Error: ${errorMsg}`);
    console.log("--------------------------------------------------");

    if (options.format.toLowerCase() === "json" && options.stdout) {
      console.log(JSON.stringify({
        status: "FAILED",
        platform: "youtube",
        videoId,
        title,
        language: null,
        elapsedTime,
        error: errorMsg
      }, null, 2));
    }
    process.exit(1);
  }
}

main();
