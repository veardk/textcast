"""Ingest: turn a URL / subtitle file / text file into the unified IR (cues + segments)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from tc_common import ends_sentence, guess_lang, text_units

MEDIA_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus"}
SUB_EXT = {".srt", ".vtt", ".json", ".json3"}
TEXT_EXT = {".txt", ".md", ".markdown"}


class IngestError(Exception):
    pass


# ---------------------------------------------------------------- subtitle parsers

_TS = re.compile(
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{3})"
)
_TAG = re.compile(r"<[^>]+>")


def _ms(h, m, s, ms) -> int:
    return ((int(h or 0) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_timed_text(text: str) -> list[dict]:
    """SRT and WebVTT share the `start --> end` cue structure."""
    cues, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = _TS.search(lines[i])
        i += 1
        if not m:
            continue
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(_TAG.sub("", lines[i]).strip())
            i += 1
        body = [re.sub(r"^[-–—]\s+", ">> ", ln) if k else ln for k, ln in enumerate(body)]  # 2nd speaker line
        cues.append({"start_ms": _ms(*m.groups()[:4]), "end_ms": _ms(*m.groups()[4:]), "text": " ".join(body)})
    return dedupe_rolling(cues)


def dedupe_rolling(cues: list[dict]) -> list[dict]:
    """YouTube auto-caption VTT repeats the previous line in each cue; keep only new text."""
    out, prev = [], ""
    for c in cues:
        t = c["text"].strip()
        if prev and t.startswith(prev):
            t = t[len(prev):].strip()
        if t:
            out.append({**c, "text": t})
            prev = c["text"].strip()
    return out


def parse_json_subs(raw) -> list[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("events"), list):  # YouTube json3
        cues = []
        for ev in raw["events"]:
            if "tStartMs" not in ev or "segs" not in ev:
                continue
            text = " ".join("".join(s.get("utf8", "") for s in ev["segs"]).split())
            if text:
                cues.append({"start_ms": ev["tStartMs"], "end_ms": ev["tStartMs"] + ev.get("dDurationMs", 0), "text": text})
        return cues
    if isinstance(raw, dict) and isinstance(raw.get("segments"), list):  # base-*-transcript.mjs -f json
        return [
            {"start_ms": round(x["start"] * 1000), "end_ms": round(x["end"] * 1000), "text": x["text"].strip()}
            for x in raw["segments"] if str(x.get("text", "")).strip()
        ]
    if isinstance(raw, dict) and isinstance(raw.get("body"), list):  # Bilibili subtitle JSON
        return [
            {"start_ms": round(b["from"] * 1000), "end_ms": round(b["to"] * 1000), "text": b["content"].strip()}
            for b in raw["body"] if b.get("content", "").strip()
        ]
    raise IngestError("Unrecognised JSON subtitle format (expected YouTube json3 or Bilibili body[])")


def parse_subtitle_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in (".json", ".json3") or text.lstrip().startswith(("{", "[")):
        cues = parse_json_subs(json.loads(text))
    else:
        cues = parse_timed_text(text)
    cues = [c for c in cues if c["text"]]
    if not cues:
        raise IngestError(f"No timed cues found in {path}")
    return sorted(cues, key=lambda c: c["start_ms"])


# ---------------------------------------------------------------- symbol cleanup
# Captions and markup carry symbols that are not part of what was said or written: speaker-change
# marks (>>, a leading "-"), sound tags ([Music], ♪), markdown syntax. The page shows words only;
# a speaker change becomes a paragraph break (cue["turn"]) instead of a visible symbol.

_TURN = re.compile(r"\s*>{2,}\s*")
_SOUND = re.compile(r"\[[^\]]*\]|[♪♫]+")
_LEAD_DASH = re.compile(r"^[-–—]\s+")


def clean_cues(cues: list[dict]) -> list[dict]:
    """Timed cues: drop caption symbols, turn `>>` / leading dashes into `turn` flags.

    A cue holding a mid-cue `>>` is split there; its time range is divided in proportion to the
    text length, so the inner boundary is approximate (never beyond the original cue's range).
    """
    out, carry = [], False
    for c in cues:
        text = _SOUND.sub(" ", c["text"])
        if re.fullmatch(r"\s*\([^)]*\)\s*", text):  # whole cue is a description, e.g. (applause)
            text = ""
        parts = []  # (text, turn)
        for k, raw in enumerate(_TURN.split(text)):
            part, turn = " ".join(raw.split()), k > 0
            if _LEAD_DASH.match(part):
                part, turn = _LEAD_DASH.sub("", part), True
            if part:
                parts.append((part, turn or carry))
                carry = False
            else:
                carry = carry or turn
        total = sum(len(p) for p, _ in parts)
        done = 0
        for p, turn in parts:
            a = c["start_ms"] + round((c["end_ms"] - c["start_ms"]) * done / total)
            done += len(p)
            b = c["start_ms"] + round((c["end_ms"] - c["start_ms"]) * done / total)
            out.append({"start_ms": a, "end_ms": b, "text": p, **({"turn": True} if turn else {})})
    return out


# A sentence end inside a cue: terminal punctuation (plus closing quotes/brackets) followed by
# whitespace and more text, e.g. "...on Earth. Not everyone...".
_MID_SENT = re.compile(r"(?<=[.?!。！？…])[\"'”’」』）)\]】]*\s+(?=\S)")


def split_sentence_cues(cues: list[dict]) -> list[dict]:
    """Split each cue at the sentence ends inside it, so a segment can end where its sentence does.

    Like the `>>` split in clean_cues, the inner time boundaries are divided in proportion to text
    length, so they are approximate (never beyond the original cue's range). Text is unchanged:
    joining the parts with spaces gives the cue's text back.
    """
    out = []
    for c in cues:
        parts, last = [], 0
        for m in _MID_SENT.finditer(c["text"]):
            parts.append(c["text"][last:m.start() + len(m.group(0).rstrip())].strip())
            last = m.end()
        parts.append(c["text"][last:].strip())
        parts = [p for p in parts if p]
        if len(parts) < 2:
            out.append(c)
            continue
        total, done = sum(len(p) for p in parts), 0
        for k, p in enumerate(parts):
            a = c["start_ms"] + round((c["end_ms"] - c["start_ms"]) * done / total)
            done += len(p)
            b = c["start_ms"] + round((c["end_ms"] - c["start_ms"]) * done / total)
            out.append({"start_ms": a, "end_ms": b, "text": p, **({"turn": True} if k == 0 and c.get("turn") else {})})
    return out


def is_punctuated(cues: list[dict]) -> bool:
    """Whether a timed track carries its own sentence punctuation (most YouTube captions do)."""
    return sum(1 for c in cues if ends_sentence(c["text"]) or _MID_SENT.search(c["text"])) >= max(3, len(cues) // 10)


_MD_BULLET = re.compile(r"^\s*(?:[-*+•]\s+|>\s*)+")
_MD_RULE = re.compile(r"^\s*([-*_=])(?:\s*\1){2,}\s*$")


def _clean_md_line(line: str) -> str:
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)           # images
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)       # links keep their text
    line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)            # bold
    return " ".join(line.split())


# ---------------------------------------------------------------- text documents

def parse_text_file(path: Path) -> list[dict]:
    """Paragraph-per-cue, no timestamps. Headings and list items each become their own cue."""
    text = path.read_text(encoding="utf-8-sig")
    md = path.suffix.lower() in (".md", ".markdown")
    if md:
        text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)  # front matter
    paras = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.splitlines() if ln.strip() and not (md and _MD_RULE.match(ln))]
        if md and any(_MD_BULLET.match(ln) for ln in lines):     # list / quote: one cue per item
            paras += [_clean_md_line(_MD_BULLET.sub("", ln)) for ln in lines]
        else:
            joined = " ".join(re.sub(r"^\s*#{1,6}\s+", "", ln) for ln in lines)
            paras.append(_clean_md_line(joined) if md else " ".join(joined.split()))
    cues = [{"start_ms": None, "end_ms": None, "text": p} for p in paras if p]
    if not cues:
        raise IngestError(f"{path} is empty")
    return cues


# ---------------------------------------------------------------- online platforms
# YouTube / Bilibili / Spotify: scripts/<channel>/base-*-transcript.mjs (Node, zero dependencies).
# YouTube falls back to yt-dlp when the base script fails or is rate-limited.

def _ytdlp(*args: str) -> subprocess.CompletedProcess:
    if not shutil.which("yt-dlp"):
        raise IngestError("yt-dlp is not installed (brew install yt-dlp)")
    return subprocess.run(["yt-dlp", "--no-warnings", *args], capture_output=True, text=True)


def platform_of(url: str) -> str | None:
    if re.search(r"(youtube\.com|youtu\.be)/", url):
        return "youtube"
    if re.search(r"bilibili\.com/|b23\.tv/", url) or re.fullmatch(r"BV\w{10}", url):
        return "bilibili"
    if re.search(r"spotify\.com/(?:intl-[\w-]+/)?episode/|^spotify:episode:", url):
        return "spotify"
    if re.fullmatch(r"[\w-]{11}", url):
        return "youtube"
    return None


def normalise_url(url: str, platform: str) -> str:
    if platform == "youtube" and re.fullmatch(r"[\w-]{11}", url):
        return f"https://www.youtube.com/watch?v={url}"
    if platform == "bilibili" and re.fullmatch(r"BV\w{10}", url):
        return f"https://www.bilibili.com/video/{url}"
    return url


def track_lang(key: str) -> str:
    """'ai-zh' → zh, 'en-orig' → en, 'en-eEY6OEpapPo' → en, 'zh-Hans' → zh-Hans."""
    parts = re.sub(r"^ai-", "", key).split("-")
    keep = [parts[0]] + [x for x in parts[1:2] if re.fullmatch(r"[A-Za-z]{2}|[A-Z][a-z]{3}", x)]
    return "-".join(keep)


def pick_track(info: dict, wanted: str | None) -> tuple[str, str]:
    """Return (lang_key, kind). Prefer human subtitles in the spoken language, then its auto track."""
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k not in ("live_chat", "danmaku")}
    auto = info.get("automatic_captions") or {}
    spoken = wanted or info.get("language")

    def match(tracks: dict, lang: str | None) -> str | None:
        if not lang:
            return None
        for key in (lang, f"{lang}-orig"):
            if key in tracks:
                return key
        base = lang.split("-")[0]
        return next((k for k in tracks if k.split("-")[0] == base or k == f"ai-{base}"), None)

    if (k := match(manual, spoken)):
        return k, "manual"
    if not wanted and len(manual) == 1:
        return next(iter(manual)), "manual"
    if (k := match(auto, spoken)):
        return k, "auto"
    orig = next((k for k in auto if k.endswith("-orig")), None)
    if orig and not wanted:
        return orig, "auto"
    if manual and not wanted:  # Bilibili AI subtitles are listed as subtitles with an ai- prefix
        k = next((k for k in manual if k.startswith("ai-")), next(iter(manual)))
        return k, "auto" if k.startswith("ai-") else "manual"
    raise IngestError("No usable subtitle track" + (f" in language {wanted!r}" if wanted else ""))


SCRIPTS = Path(__file__).resolve().parent
BASE_SCRIPT = {
    "youtube": SCRIPTS / "youtube" / "base-youtube-transcript.mjs",
    "bilibili": SCRIPTS / "bilibili" / "base-bilibili-transcript.mjs",
    "spotify": SCRIPTS / "spotify" / "base-spotify-transcript.mjs",
}
BASE_TIMEOUT = {"youtube": 90, "bilibili": 330, "spotify": 150}  # Bilibili may wait up to 3 min for a QR login
# The Bilibili script saves its login cookie in the working directory; keep it out of project dirs.
BASE_CWD = Path.home() / ".textcast"


def _tail(text: str, n: int = 6) -> str:
    return " | ".join(line.strip() for line in text.strip().splitlines()[-n:] if line.strip())


def fetch_base(url: str, platform: str, work: Path, sub_lang: str | None) -> tuple[dict, list[dict]]:
    """Run the channel's base script (-f json) and read the JSON it writes."""
    node = shutil.which("node")
    if not node:
        raise IngestError("node is not installed (needed for the base transcript scripts)")
    # absolute: the script runs with cwd=BASE_CWD, so a relative -o would land in the wrong place
    work = work.resolve()
    src = work / "source"
    src.mkdir(parents=True, exist_ok=True)
    out = src / f"base-{platform}.json"
    out.unlink(missing_ok=True)
    BASE_CWD.mkdir(parents=True, exist_ok=True)
    cmd = [node, str(BASE_SCRIPT[platform]), url, "-f", "json", "-o", str(out)]
    if sub_lang:
        cmd += ["-l", sub_lang]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=BASE_TIMEOUT[platform], cwd=BASE_CWD)
    except subprocess.TimeoutExpired:
        raise IngestError(f"base-{platform}-transcript timed out after {BASE_TIMEOUT[platform]}s") from None
    log = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0 or not out.exists():
        err = re.search(r"^Error: (.+)$", log, re.M)
        raise IngestError(err.group(1) if err else (_tail(log) or "base script failed"))

    raw = json.loads(out.read_text(encoding="utf-8"))
    cues = parse_subtitle_file(out)
    code = raw.get("langCode") or ""
    auto = bool(raw.get("isAutoGenerated") or raw.get("isAiGenerated"))
    meta = {
        "source_type": platform,
        "title": raw.get("title") or "",
        "duration_ms": cues[-1]["end_ms"],
        "subtitle_kind": "auto" if auto else "manual",
        "subtitle_lang": code,
        "subtitle_file": str(out.relative_to(work)),
        "source_lang_guess": track_lang(code) if code else None,
        "fetcher": f"base-{platform}-transcript",
    }
    if platform == "youtube":
        vid = raw.get("videoId") or ""
        meta.update(video_id=vid, source_url=f"https://www.youtube.com/watch?v={vid}")
    elif platform == "spotify":
        ep = raw.get("episodeId") or ""
        meta.update(video_id=ep, uploader=raw.get("showName") or "", source_url=f"https://open.spotify.com/episode/{ep}")
    else:
        bv = raw.get("bvid") or ""
        page = int(raw.get("page") or 1)
        meta.update(video_id=bv, bili_page=page,
                    source_url=f"https://www.bilibili.com/video/{bv}" + (f"?p={page}" if page > 1 else ""))
    return meta, cues


def fetch_ytdlp(url: str, platform: str, work: Path, sub_lang: str | None) -> tuple[dict, list[dict]]:
    """YouTube fallback: yt-dlp metadata + subtitle download."""
    res = _ytdlp("-J", "--skip-download", url)
    if res.returncode != 0:
        raise IngestError(f"yt-dlp metadata failed: {res.stderr.strip()[-400:]}")
    info = json.loads(res.stdout)
    key, kind = pick_track(info, sub_lang)

    src = work / "source"
    src.mkdir(parents=True, exist_ok=True)
    for old in src.glob("sub.*"):
        old.unlink()
    flag = "--write-subs" if kind == "manual" else "--write-auto-subs"
    res = _ytdlp("--skip-download", flag, "--sub-langs", key, "--sub-format", "json3/srt/vtt/best",
                 "-o", str(src / "sub.%(ext)s"), url)
    files = [f for f in src.glob("sub.*") if f.suffix.lower() in SUB_EXT]
    if res.returncode != 0 or not files:
        raise IngestError(f"yt-dlp subtitle download failed: {res.stderr.strip()[-400:]}")
    cues = parse_subtitle_file(files[0])
    meta = {
        "source_type": platform,
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "upload_date": info.get("upload_date") or "",
        "source_url": info.get("webpage_url") or url,
        "video_id": info.get("id") or "",
        "duration_ms": int((info.get("duration") or 0) * 1000) or cues[-1]["end_ms"],
        "subtitle_kind": kind,
        "subtitle_lang": key,
        "subtitle_file": str(files[0].relative_to(work)),
        "source_lang_guess": track_lang(key),
        "fetcher": "yt-dlp",
    }
    return meta, cues


def fetch_online(url: str, platform: str, work: Path, sub_lang: str | None) -> tuple[dict, list[dict]]:
    url = normalise_url(url, platform)
    try:
        return fetch_base(url, platform, work, sub_lang)
    except IngestError as base_err:
        if platform != "youtube":
            hint = (" If it asks for login: run `node scripts/bilibili/base-bilibili-transcript.mjs --sync-browser`"
                    " (or `--login`) once, then retry. Or pass a subtitle file instead.")
            raise IngestError(f"{str(base_err).rstrip('.')}.{hint}" if platform == "bilibili" else str(base_err)) from None
        print(f"[textcast] base-youtube-transcript failed ({base_err}); falling back to yt-dlp", file=sys.stderr)
        try:
            meta, cues = fetch_ytdlp(url, platform, work, sub_lang)
        except IngestError as e:
            raise IngestError(f"YouTube fetch failed — base script: {str(base_err).rstrip('.')}; yt-dlp fallback: {e}") from None
        meta["fallback_reason"] = str(base_err)
        return meta, cues


# ---------------------------------------------------------------- segmentation

def build_segments(cues: list[dict], timed: bool) -> list[dict]:
    """Deterministically merge cues into sentence-sized reading segments.

    Every cue lands in exactly one segment, in order. Segments are the unit you
    translates and the unit topic boundaries snap to.
    """
    if not timed:
        return [{"id": i, "cues": [i, i], "start_ms": None, "end_ms": None, "text": c["text"]}
                for i, c in enumerate(cues)]

    # A track that carries its own punctuation (most YouTube captions) is cut only at real sentence
    # ends, so a segment is a whole sentence: the length, cue-count and pause limits that split a
    # sentence in half apply only to unpunctuated tracks (e.g. Chinese ASR), which have no other
    # boundary to go by. A hard length/time ceiling still keeps runaway sentences seekable.
    punctuated = is_punctuated(cues)
    segs, cur = [], []

    def close():
        text = " ".join(c["text"] for c in cur)
        turn = bool(cur[0].get("turn"))
        if any(ord(ch) > 0x2E80 for ch in text):
            text = re.sub(r"(?<=[^\x00-\x7f]) (?=[^\x00-\x7f])", "", text)
        segs.append({"id": len(segs), "cues": [cur[0]["i"], cur[-1]["i"]],
                     "start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"], "text": text,
                     **({"turn": True} if turn else {})})
        cur.clear()

    for k, c in enumerate(cues):
        if cur and c.get("turn"):  # speaker change always starts a new segment
            close()
        cur.append({**c, "i": k})
        units = sum(text_units(x["text"]) for x in cur)
        nxt = cues[k + 1] if k + 1 < len(cues) else None
        pause = (nxt["start_ms"] - c["end_ms"]) if nxt else 0
        if punctuated:
            span = c["end_ms"] - cur[0]["start_ms"]
            boundary = (ends_sentence(c["text"]) and (units >= 120 or pause >= 1500)) or pause >= 4000 or units >= 600 or span >= 40_000
        else:
            boundary = (ends_sentence(c["text"]) and units >= 20) or pause >= 1500 or units >= 240 or len(cur) >= 8
        if boundary:
            close()
    if cur:
        close()
    return segs


# ---------------------------------------------------------------- entry

def ingest(source: str, work: Path, sub_lang: str | None = None, media: str | None = None, title: str | None = None) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    platform = platform_of(source)
    path = Path(source).expanduser()

    if platform and not path.exists():
        meta, cues = fetch_online(source, platform, work, sub_lang)
    elif path.is_file() and path.suffix.lower() in MEDIA_EXT:
        raise IngestError("Local audio/video transcription (faster-whisper) is not implemented yet. "
                          "Supply a subtitle file for it and pass --media to keep click-to-seek.")
    elif path.is_file() and path.suffix.lower() in SUB_EXT:
        cues = parse_subtitle_file(path)
        meta = {"source_type": "subtitle", "title": path.stem, "subtitle_kind": "file",
                "subtitle_file": str(path.resolve()), "duration_ms": cues[-1]["end_ms"]}
    elif path.is_file() and path.suffix.lower() in TEXT_EXT:
        cues = parse_text_file(path)
        meta = {"source_type": "text", "title": path.stem, "subtitle_kind": "none",
                "text_file": str(path.resolve()), "duration_ms": None}
    elif path.is_file():
        raise IngestError(f"Unsupported file type {path.suffix!r}. For PDF / web pages, extract the text "
                          "to a .md file first, then ingest that.")
    else:
        raise IngestError(f"Not a supported URL or existing file: {source}")

    timed = cues[0]["start_ms"] is not None
    if timed:
        cues = clean_cues(cues)
        if is_punctuated(cues):
            cues = split_sentence_cues(cues)
        if not cues:
            raise IngestError("The subtitle track has no text after removing caption symbols")
    meta["has_timestamps"] = timed
    if title:
        meta["title"] = title
    if media:
        mp = Path(media).expanduser().resolve()
        if not mp.exists():
            raise IngestError(f"--media file not found: {mp}")
        meta["media_file"] = str(mp)
    meta.setdefault("source_lang_guess", None)
    meta["source_lang_guess"] = meta["source_lang_guess"] or guess_lang(" ".join(c["text"] for c in cues[:300]))

    for i, c in enumerate(cues):
        c["i"] = i
    ir = {"version": 1, "meta": meta, "cues": cues, "segments": build_segments(cues, timed)}
    return ir


if __name__ == "__main__":
    print("Use textcast.py ingest", file=sys.stderr)
    sys.exit(2)
