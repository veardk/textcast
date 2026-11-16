#!/usr/bin/env node
/**
 * Bilibili Transcript Extractor (Zero-Dependency Node.js Edition)
 * 
 * Features:
 *  - Native WBI signature encryption (nav mixinKey + MD5 w_rid + wts)
 *  - Multi-page video support (?p=X)
 *  - Multi-language fallback: prioritized by user input -> 'en' -> i18n ranking -> first available
 *  - Auto Browser Cookie Sync: automatically detects and extracts logged-in Bilibili credentials
 *    from your local browser (Chrome, Edge, Safari, Brave, Firefox, etc.) without manual F12 copying
 *  - Output formats: srt, vtt, txt, md, json
 * 
 * Usage:
 *  node base-bilibili-transcript.mjs <VideoURL_or_BVID> [options]
 * 
 * Options:
 *  -f, --format <srt|vtt|txt|md|json>  Output format (default: srt)
 *  -o, --output <file_path>             Custom output file path
 *  -p, --page <page_number>             Page index for multi-part videos (default: 1)
 *  -l, --lang <lang_code>               Specified language code (e.g., en, zh-CN)
 *  -c, --cookie <SESSDATA>              Manual SESSDATA override
 *  --sync-browser                       Manually sync logged-in cookie from local browser
 *  --login                              Trigger QR code login directly in browser
 *  --stdout                             Print to console without saving to disk
 *  -h, --help                           Show help message
 */

import { exec } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";

const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36";
const COOKIE_FILE_PATH = path.resolve(process.cwd(), ".bilibili-cookie.json");
const LEGACY_COOKIE_FILE_PATH = path.join(os.homedir(), ".bilibili-transcript-cookie.json");
const SUPPORTED_BROWSERS = ["chrome", "edge", "safari", "brave", "firefox", "opera", "vivaldi"];

const BILI_MIXIN_TAB = [
  46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
  33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
  61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
  36, 20, 34, 44, 52
];

// Standard i18n priority fallback chain (English first, followed by major world languages)
const I18N_FALLBACK_ORDER = [
  "en", "en-US", "en-GB",
  "zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW",
  "es", "ja", "ko", "fr", "de", "ru", "pt", "it"
];

// Open URL in system default browser (cross-platform)
function openBrowser(url) {
  const platform = process.platform;
  if (platform === "darwin") {
    exec(`open "${url}"`);
  } else if (platform === "win32") {
    exec(`cmd /c start "" "${url}"`);
  } else {
    exec(`xdg-open "${url}"`);
  }
}

// Convert AV number to BV
function avToBv(aid) {
  const table = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf";
  const out = [..."BV1000000000"];
  let n = ((1n << 51n) | BigInt(aid)) ^ 23442827791579n;
  for (let i = 11; n > 0n; i--, n /= 58n) out[i] = table[Number(n % 58n)];
  [out[3], out[9]] = [out[9], out[3]];
  [out[4], out[7]] = [out[7], out[4]];
  return out.join("");
}

// Extract BVID
function extractBvid(input) {
  const text = String(input || "").trim();
  const fromPath = text.match(/\/video\/(BV[0-9A-Za-z]+)/)?.[1];
  if (fromPath) return fromPath;
  const avFromPath = text.match(/\/video\/av(\d+)/i)?.[1];
  if (avFromPath) return avToBv(avFromPath);
  const fromQuery = text.match(/[?&]bvid=([0-9A-Za-z]+)/)?.[1];
  if (fromQuery && /^BV[0-9A-Za-z]+$/.test(fromQuery)) return fromQuery;
  const matchDirect = text.match(/^(BV[0-9A-Za-z]+)$/);
  if (matchDirect) return matchDirect[1];
  return "";
}

// Extract multi-page index
function extractPage(input, defaultPage = 1) {
  const match = String(input).match(/[?&]p=(\d+)/);
  return match ? parseInt(match[1], 10) : defaultPage;
}

// Calculate WBI Mixin Key
function getMixinKey(rawKey) {
  return BILI_MIXIN_TAB.map((n) => rawKey[n]).join("").slice(0, 32);
}

// Generate WBI Signature
function signWbi(params, mixinKey) {
  const wts = Math.floor(Date.now() / 1000);
  const curr = { ...params, wts };
  const query = Object.keys(curr)
    .sort()
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(String(curr[k]).replace(/[!\x27()*]/g, ""))}`)
    .join("&");
  const w_rid = crypto.createHash("md5").update(query + mixinKey).digest("hex");
  return `${query}&w_rid=${w_rid}`;
}

// Read saved Cookie from .bilibili-cookie.json (relative path)
async function loadPersistedCookie() {
  try {
    const raw = await fs.readFile(COOKIE_FILE_PATH, "utf-8");
    const json = JSON.parse(raw);
    return json.sessdata || "";
  } catch {
    // Check legacy file if available and migrate
    try {
      const rawLegacy = await fs.readFile(LEGACY_COOKIE_FILE_PATH, "utf-8");
      const jsonLegacy = JSON.parse(rawLegacy);
      if (jsonLegacy.sessdata) {
        await savePersistedCookie(jsonLegacy);
        await fs.unlink(LEGACY_COOKIE_FILE_PATH).catch(() => {});
        return jsonLegacy.sessdata;
      }
    } catch {}
    return "";
  }
}

// Save Cookie to ~/.bilibili-transcript-cookie.json
async function savePersistedCookie(data) {
  try {
    await fs.writeFile(COOKIE_FILE_PATH, JSON.stringify(data, null, 2), "utf-8");
  } catch (err) {
    console.warn(`[!] Warning: Failed to save cookie to ${COOKIE_FILE_PATH}: ${err.message}`);
  }
}

// Automatically extract logged-in Bilibili SESSDATA from local browsers
async function extractCookieFromLocalBrowsers() {
  const tmpFile = path.join(os.tmpdir(), `bili_cookie_${Date.now()}.txt`);

  for (const browser of SUPPORTED_BROWSERS) {
    try {
      await new Promise((resolve) => {
        exec(
          `yt-dlp --cookies-from-browser ${browser} --cookies "${tmpFile}" --skip-download "https://www.bilibili.com" 2>/dev/null`,
          () => resolve()
        );
      });

      const content = await fs.readFile(tmpFile, "utf-8").catch(() => "");
      const match = content.match(/\.bilibili\.com\s+(?:TRUE|FALSE)\s+\/\s+(?:TRUE|FALSE)\s+\d+\s+SESSDATA\s+([^\s]+)/);
      if (match && match[1]) {
        const sessdata = decodeURIComponent(match[1]);
        await savePersistedCookie({
          sessdata,
          sourceBrowser: browser,
          updatedAt: new Date().toISOString()
        });
        await fs.unlink(tmpFile).catch(() => {});
        return { sessdata, browser };
      }
    } catch {
      // Continue to next browser
    }
  }

  await fs.unlink(tmpFile).catch(() => {});
  return null;
}

// Interactive QR code login fallback
async function performBrowserLogin() {
  console.log("\n--------------------------------------------------");
  console.log("[*] Requesting Bilibili QR code for browser login...");

  const genRes = await fetch("https://passport.bilibili.com/x/passport-login/web/qrcode/generate", {
    headers: { "User-Agent": USER_AGENT }
  });
  const genJson = await genRes.json();
  if (genJson.code !== 0 || !genJson.data?.qrcode_key) {
    throw new Error(`Failed to generate login QR code: [${genJson.code}] ${genJson.message}`);
  }

  const { url, qrcode_key } = genJson.data;

  console.log("[*] Opening your default browser for one-click scan authorization...");
  console.log(`    URL: ${url}`);
  openBrowser(url);

  console.log("[*] Waiting for Bilibili App scan confirmation (Press Ctrl+C to cancel)...");

  const startTime = Date.now();
  const timeoutMs = 180 * 1000; // 3 minutes timeout

  while (Date.now() - startTime < timeoutMs) {
    await new Promise((r) => setTimeout(r, 1500));

    const pollRes = await fetch(`https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=${qrcode_key}`, {
      headers: { "User-Agent": USER_AGENT }
    });
    const pollJson = await pollRes.json();
    const code = pollJson.data?.code;

    if (code === 0) {
      let sessdata = "";
      const crossUrl = pollJson.data?.url;
      if (crossUrl) {
        try {
          const parsed = new URL(crossUrl);
          sessdata = parsed.searchParams.get("SESSDATA") || "";
        } catch {}
      }

      if (!sessdata) {
        const cookies = pollRes.headers.getSetCookie?.() || [];
        for (const c of cookies) {
          const m = c.match(/SESSDATA=([^;]+)/);
          if (m) {
            sessdata = m[1];
            break;
          }
        }
      }

      if (!sessdata) {
        throw new Error("Logged in successfully but could not extract SESSDATA cookie.");
      }

      await savePersistedCookie({
        sessdata,
        sourceBrowser: "qrcode",
        updatedAt: new Date().toISOString()
      });

      console.log(`[+] Authorization SUCCESS!`);
      console.log(`    Cookie persisted to: ${COOKIE_FILE_PATH}`);
      console.log("--------------------------------------------------\n");
      return sessdata;
    } else if (code === 86038) {
      throw new Error("QR code expired. Please run the script again.");
    } else if (code === 86090) {
      process.stdout.write("\r[*] Scanned! Please tap 'Confirm' on your Bilibili App...  ");
    }
  }

  throw new Error("Login timed out after 3 minutes.");
}

// Select track based on language priority: User input -> English -> i18n list -> First available
function pickTrackByPriority(subtitles, preferredLang = "") {
  if (!subtitles.length) return null;
  const normalize = (val) => String(val || "").toLowerCase().replace(/^ai-/, "");

  // 1. User explicitly specified language
  if (preferredLang) {
    const target = preferredLang.toLowerCase();
    const userMatch = subtitles.find((s) => {
      const code = normalize(s.lan);
      const doc = String(s.lan_doc || "").toLowerCase();
      return code === target || code.startsWith(target) || doc.includes(target);
    });
    if (userMatch) return userMatch;
  }

  // 2. Iterate through i18n order (en is #1)
  for (const lang of I18N_FALLBACK_ORDER) {
    const target = lang.toLowerCase();
    const match = subtitles.find((s) => {
      const code = normalize(s.lan);
      const doc = String(s.lan_doc || "").toLowerCase();
      if (code === target || code.startsWith(`${target}-`) || (target.length === 2 && code.startsWith(target))) return true;
      if (target === "en" && (doc.includes("英语") || doc.includes("english"))) return true;
      if (target.startsWith("zh") && (doc.includes("中文") || doc.includes("汉语") || doc.includes("国语"))) return true;
      return false;
    });
    if (match) return match;
  }

  // 3. Fallback to whatever language is available
  return subtitles[0];
}

async function fetchBilibiliTranscript(bvid, { page = 1, sessdata = "", preferredLang = "" } = {}) {
  const headers = {
    "User-Agent": USER_AGENT,
    Referer: "https://www.bilibili.com"
  };
  if (sessdata) {
    headers.Cookie = `SESSDATA=${sessdata}`;
  }

  // 1. Fetch video metadata
  const viewRes = await fetch(`https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`, { headers });
  const view = await viewRes.json();
  if (view.code !== 0) {
    throw { message: `Video metadata request failed: [${view.code}] ${view.message || "Unknown error"}`, title: "Unknown" };
  }

  const title = view.data.title;
  const aid = String(view.data.aid);
  const pages = view.data.pages || [];
  const targetPage = pages[page - 1] || pages[0] || {};
  const cid = String(targetPage.cid || view.data.cid);
  const pageTitle = pages.length > 1 ? ` (P${targetPage.page || page} - ${targetPage.part || ""})` : "";
  const fullTitle = `${title}${pageTitle}`;

  // 2. Acquire WBI encryption key
  let mixinKey = "";
  try {
    const navRes = await fetch("https://api.bilibili.com/x/web-interface/nav", { headers });
    const nav = await navRes.json();
    const imgUrl = nav.data?.wbi_img?.img_url || "";
    const subUrl = nav.data?.wbi_img?.sub_url || "";
    const imgKey = imgUrl.split("/").pop()?.split(".")[0] || "";
    const subKey = subUrl.split("/").pop()?.split(".")[0] || "";
    if (imgKey && subKey) {
      mixinKey = getMixinKey(imgKey + subKey);
    }
  } catch {}

  const requestUrls = [];
  if (mixinKey) {
    const query = signWbi({ aid, cid, bvid }, mixinKey);
    requestUrls.push(`https://api.bilibili.com/x/player/wbi/v2?${query}`);
  }
  requestUrls.push(`https://api.bilibili.com/x/player/v2?aid=${aid}&cid=${cid}&bvid=${bvid}`);

  let player = null;
  for (const url of requestUrls) {
    try {
      const res = await fetch(url, { headers: { ...headers, Referer: `https://www.bilibili.com/video/${bvid}` } });
      const text = await res.text();
      if (text.trim().startsWith("{")) {
        const json = JSON.parse(text);
        if (json.code === 0) {
          player = json;
          break;
        }
      }
    } catch {}
  }

  if (!player || player.code !== 0) {
    throw { message: `Player API responded with error: ${player?.message || "All player endpoints failed"}`, title: fullTitle };
  }

  const data = player.data || {};
  const subtitles = data.subtitle?.subtitles || [];

  if (!subtitles.length) {
    if (data.need_login_subtitle) {
      throw {
        needsLogin: true,
        message: "Subtitle access is restricted by Bilibili login policy (need_login_subtitle: true).",
        title: fullTitle
      };
    }
    throw { message: "No subtitle tracks available for this video (neither manual nor AI generated).", title: fullTitle };
  }

  const selected = pickTrackByPriority(subtitles, preferredLang);
  if (!selected || !selected.subtitle_url) {
    throw { message: "Selected subtitle track has no valid URL.", title: fullTitle };
  }
  let subUrl = selected.subtitle_url;
  if (subUrl.startsWith("//")) subUrl = "https:" + subUrl;
  if (!subUrl.startsWith("http")) subUrl = "https://" + subUrl;

  // 3. Download CDN subtitle JSON
  const cdnRes = await fetch(subUrl, { headers });
  const cdnJson = await cdnRes.json();
  const rawBody = cdnJson.body || [];

  const segments = rawBody.map((item) => ({
    start: Number(item.from) || 0,
    end: Number(item.to) || 0,
    text: String(item.content || "").trim()
  })).filter((seg) => seg.text);

  if (!segments.length) {
    throw { message: "Subtitle file was fetched but contained empty segments.", title: fullTitle };
  }

  const langLabel = selected.lan_doc ? `${selected.lan} (${selected.lan_doc})` : selected.lan;

  return {
    platform: "bilibili",
    bvid,
    aid,
    cid,
    page: targetPage.page || page,
    title: fullTitle,
    language: langLabel,
    langCode: selected.lan,
    isAiGenerated: String(selected.lan || "").startsWith("ai-"),
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
        `> Source: Bilibili (${data.bvid}) | Language: ${data.language} | Segments: ${segments.length}\n\n` +
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
    page: 1,
    lang: "",
    cookie: "",
    loginOnly: false,
    syncBrowserOnly: false,
    stdout: false
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-f" || arg === "--format") {
      options.format = args[++i];
    } else if (arg === "-o" || arg === "--output") {
      options.output = args[++i];
    } else if (arg === "-p" || arg === "--page") {
      options.page = parseInt(args[++i], 10) || 1;
    } else if (arg === "-l" || arg === "--lang") {
      options.lang = args[++i];
    } else if (arg === "-c" || arg === "--cookie") {
      options.cookie = args[++i];
    } else if (arg === "--sync-browser") {
      options.syncBrowserOnly = true;
    } else if (arg === "--login") {
      options.loginOnly = true;
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
Bilibili Transcript Extractor (Zero-Dependency Node.js)

Usage:
  node base-bilibili-transcript.mjs <VideoURL_or_BVID> [options]

Examples:
  node base-bilibili-transcript.mjs BV1TgWp6MEHJ
  node base-bilibili-transcript.mjs "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
  node base-bilibili-transcript.mjs BV1xx411c7mD -f md -o note.md
  node base-bilibili-transcript.mjs --sync-browser

Options:
  -f, --format <srt|vtt|txt|md|json>  Output format (default: srt)
  -o, --output <path>                  Custom output file path
  -p, --page <number>                  Page index for multi-part videos (default: 1)
  -l, --lang <lang_code>               Preferred language code (e.g., en, zh-CN)
  -c, --cookie <SESSDATA>              Manual SESSDATA override
  --sync-browser                       Extract logged-in cookie from Chrome/Edge/Safari/Firefox
  --login                              QR code scan login fallback
  --stdout                             Output to stdout directly without saving
  -h, --help                           Show this help message
`);
}

async function main() {
  const options = parseCliArgs();

  // If user calls --sync-browser explicitly
  if (options.syncBrowserOnly) {
    console.log("[*] Searching local browsers (Chrome, Edge, Safari, Brave, Firefox) for Bilibili login cookie...");
    const found = await extractCookieFromLocalBrowsers();
    if (found) {
      console.log(`[+] Successfully found logged-in Bilibili session in ${found.browser.toUpperCase()}!`);
      console.log(`Saved To: ${COOKIE_FILE_PATH}`);
    } else {
      console.log(`[-] No logged-in Bilibili cookie found in local browsers.`);
      console.log(`Note: Please make sure you are logged in to bilibili.com in your browser.`);
    }
    process.exit(0);
  }

  // If user invokes --login directly
  if (options.loginOnly) {
    try {
      await performBrowserLogin();
      process.exit(0);
    } catch (err) {
      console.error(`\nError: Login failed: ${err.message}`);
      process.exit(1);
    }
  }

  if (!options.input) {
    printHelp();
    process.exit(1);
  }

  const bvid = extractBvid(options.input);
  if (!bvid) {
    console.error("Error: Invalid Bilibili BVID or video URL.");
    process.exit(1);
  }

  const page = extractPage(options.input, options.page);
  const startTime = Date.now();

  // 1. Resolve cookie priority: CLI arg -> Env var -> Local saved file
  let cookie = options.cookie || process.env.BILI_SESSDATA || (await loadPersistedCookie());

  // 2. If no cookie yet, automatically try to sync from local browser
  if (!cookie) {
    const extracted = await extractCookieFromLocalBrowsers();
    if (extracted) {
      cookie = extracted.sessdata;
      console.log(`[*] Auto-detected logged-in Bilibili session from ${extracted.browser.toUpperCase()}.`);
    }
  }

  console.log(`[*] Processing Bilibili Video: ${bvid} (Part ${page})...`);

  try {
    let result;
    try {
      result = await fetchBilibiliTranscript(bvid, {
        page,
        sessdata: cookie,
        preferredLang: options.lang
      });
    } catch (err) {
      // If error indicates login required, auto-sync from browser or trigger prompt
      if (err.needsLogin) {
        console.log(`\n[!] This video requires login to unlock subtitles.`);
        console.log(`[*] Checking local browsers (Chrome, Edge, Safari, etc.) for existing login...`);
        const extracted = await extractCookieFromLocalBrowsers();
        if (extracted) {
          console.log(`[+] Found logged-in session in ${extracted.browser.toUpperCase()}! Retrying...`);
          cookie = extracted.sessdata;
          result = await fetchBilibiliTranscript(bvid, {
            page,
            sessdata: cookie,
            preferredLang: options.lang
          });
        } else {
          // If browser is not logged in either, launch QR code
          console.log(`[*] No logged-in browser session found. Launching QR authorization...`);
          cookie = await performBrowserLogin();
          result = await fetchBilibiliTranscript(bvid, {
            page,
            sessdata: cookie,
            preferredLang: options.lang
          });
        }
      } else {
        throw err;
      }
    }

    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(2);
    const elapsedTime = `${elapsedSec}s`;

    // Standardized English response summary
    console.log("--------------------------------------------------");
    console.log(`Status: SUCCESS`);
    console.log(`Title: ${result.title}`);
    console.log(`Language: ${result.language}${result.isAiGenerated ? " (AI-Generated)" : ""}`);
    console.log(`Elapsed Time: ${elapsedTime}`);
    console.log(`Segments: ${result.segments.length}`);
    console.log("--------------------------------------------------");

    const payload = {
      status: "SUCCESS",
      platform: "bilibili",
      bvid,
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
    const defaultFilename = `[Bilibili]_${sanitizeFilename(result.title)}.${ext}`;
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
        platform: "bilibili",
        bvid,
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
