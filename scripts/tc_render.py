"""Render: IR + enrich + translations → self-contained transcript / summary pages."""
import html
import json
import os
import re
from pathlib import Path

from tc_common import ends_sentence, fmt_dur, fmt_ts, is_cjk_lang, is_rtl, lang_name, same_lang, text_units
from tc_template import TPL, render

N_SPEAKER_COLORS = 6  # --spk-0 … --spk-5 in base.css, defined per theme
GAP_MS, BIG_GAP_MS = 15_000, 60_000
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus"}


def load_bundles() -> dict:
    return json.loads((TPL / "i18n.json").read_text(encoding="utf-8"))


def ui_locale(code: str | None, bundles: dict) -> str:
    """Pick the UI string bundle for a language; languages without a bundle fall back to English."""
    c = (code or "").lower()
    if c.startswith("zh"):
        return "zh-Hant" if any(t in c for t in ("tw", "hk", "mo", "hant")) else "zh"
    base = c.split("-")[0]
    return base if base in bundles else "en"


def esc(text) -> str:
    return html.escape(str(text or "").strip(), quote=True)


def md_inline(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


# ---------------------------------------------------------------- shared context

class Ctx:
    def __init__(self, ir: dict, enrich: dict, tr: dict, out_dir: Path, links: dict):
        """out_dir: folder the page is written to (local media paths are made relative to it).
        links: {"transcript": file|None, "summary": file|None, "index": path|None} relative to out_dir."""
        self.ir, self.enrich, self.tr, self.out_dir, self.links = ir, enrich, tr, out_dir, links
        self.meta = ir["meta"]
        self.segs = ir["segments"]
        self.timed = self.meta["has_timestamps"]
        self.long = (self.meta.get("duration_ms") or 0) >= 3600_000
        self.src_lang = enrich["source_lang"]
        self.tgt_lang = enrich["target_lang"]
        self.translated = not same_lang(self.src_lang, self.tgt_lang)
        self.modes = ["bi", "tgt", "src"] if self.translated else ["src"]
        # UI chrome follows the language the analysis is written in (the target), not the source
        self.ui_lang = enrich.get("ui_lang") or self.tgt_lang
        bundles = load_bundles()
        self.locale = ui_locale(self.ui_lang, bundles)
        if self.locale == "en" and not self.ui_lang.lower().startswith("en"):
            self.ui_lang = "en"  # no bundle for this language: the page chrome is English, say so
        self.s = {**bundles["en"], **bundles[self.locale]}
        self.player = self._player()
        self.speaker = self._speakers()
        ps = enrich.get("paragraphs")
        self.para_starts = {i for i in ps if isinstance(i, int)} if isinstance(ps, list) and ps else None

    def ts(self, ms) -> str:
        return fmt_ts(ms, self.long)

    def topics(self):
        topics = self.enrich["topics"]
        for k, t in enumerate(topics):
            end = topics[k + 1]["from_seg"] if k + 1 < len(topics) else len(self.segs)
            yield k + 1, t, self.segs[t["from_seg"]:end]

    def span(self, segs) -> str:
        if self.timed:
            return f"{self.ts(segs[0]['start_ms'])} – {self.ts(segs[-1]['end_ms'])}"
        return f"¶ {segs[0]['id'] + 1}–{segs[-1]['id'] + 1}"

    def _player(self):
        m = self.meta
        if not self.timed:
            return None
        if m.get("media_file"):
            rel = os.path.relpath(m["media_file"], self.out_dir.resolve())
            kind = "audio" if Path(rel).suffix.lower() in AUDIO_EXT else "video"
            return {"kind": kind, "src": Path(rel).as_posix()}
        if m["source_type"] == "youtube" and m.get("video_id"):
            return {"kind": "youtube", "id": m["video_id"]}
        if m["source_type"] == "bilibili" and m.get("video_id"):
            return {"kind": "bilibili", "id": m["video_id"], "page": m.get("bili_page", 1)}
        return None

    def _speakers(self) -> list:
        names = [None] * len(self.segs)
        ranges = self.enrich.get("speakers") or []
        for k, sp in enumerate(ranges):
            end = ranges[k + 1]["from_seg"] if k + 1 < len(ranges) else len(self.segs)
            for i in range(sp["from_seg"], end):
                names[i] = sp.get("name")
        order = list(dict.fromkeys(n for n in names if n))
        self.colors = {n: f"var(--spk-{i % N_SPEAKER_COLORS})" for i, n in enumerate(order)}
        return names

    def text(self, seg, side: str) -> str:
        return seg["text"] if side == "src" else self.tr.get(str(seg["id"]), "")

    def t(self, key: str, **kw) -> str:
        return self.s[key].format(**kw) if kw else self.s[key]

    def lang(self, side: str) -> str:
        return self.src_lang if side == "src" else self.tgt_lang


# ---------------------------------------------------------------- shared page context

def ui_context(t, ui_lang: str) -> dict:
    """Values every template needs: document language/direction, theme switch labels, colon."""
    return {
        "html_lang": ui_lang,
        "html_dir": "rtl" if is_rtl(ui_lang) else "ltr",
        "theme_label": t("theme_label"),
        "theme_labels": "|".join(t("theme_" + th) for th in ("light", "dark", "sepia")),
        # non-breaking: a trailing plain space is collapsed at the end of an inline-flex label
        "colon": t("colon").replace(" ", " "),
    }


def data_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def page_context(c: Ctx, current: str) -> dict:
    """Hero, navigation and footer values shared by the transcript and summary templates."""
    m, e, L = c.meta, c.enrich, c.links
    title = e.get("title") or m.get("title") or c.t("untitled")
    src = c.s.get(f"src_{m['source_type']}", m["source_type"])
    date = m.get("upload_date") or ""
    if re.fullmatch(r"\d{8}", date):
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    url = m.get("source_url") or ""
    both = bool(L.get("transcript") and L.get("summary"))
    arrow = "←" if is_rtl(c.ui_lang) else "→"
    langs = (f"{lang_name(c.src_lang)} {arrow} {lang_name(c.tgt_lang)}" if c.translated
             else c.t("same_lang", lang=lang_name(c.src_lang)))
    tokens = [("tok_source", src, False),
              ("tok_duration", fmt_dur(m["duration_ms"]) if m.get("duration_ms") else "", False),
              ("tok_speakers", " / ".join(c.colors), False),
              ("tok_textsrc", c.s.get("badge_" + str(m.get("subtitle_kind")), ""), True),
              ("tok_lang", langs, False)]
    if current == "transcript":
        ctas = [("btn-primary", "#toc", "cta_toc")] + ([("btn-ghost", L["summary"], "cta_to_summary")] if L.get("summary") else [])
    else:
        ctas = [("btn-primary", "#outline", "cta_outline")] + ([("btn-ghost", L["transcript"], "cta_to_transcript")] if L.get("transcript") else [])
    ctas = [{"cls": cls, "href": href, "label": c.t(key), "target": "", "rel": ""} for cls, href, key in ctas]
    if url:
        ctas.append({"cls": "btn-ghost", "href": url, "label": c.t("cta_open"), "target": "_blank", "rel": "noopener noreferrer"})
    code = lambda x: f"<code>{esc(x)}</code>"  # noqa: E731
    kind = c.s.get("badge_" + str(m.get("subtitle_kind")), "")
    prov_src = {
        "youtube": lambda: c.t("prov_youtube", track=code(m.get("subtitle_lang")), kind=kind, tool=esc(m.get("fetcher", "yt-dlp"))),
        "bilibili": lambda: c.t("prov_bilibili", track=code(m.get("subtitle_lang")), kind=kind, tool=esc(m.get("fetcher", "yt-dlp"))),
        "spotify": lambda: c.t("prov_spotify", kind=kind, tool=esc(m.get("fetcher", "base-spotify-transcript"))),
        "subtitle": lambda: c.t("prov_subtitle", file=code(Path(m.get("subtitle_file", "")).name)),
        "text": lambda: c.t("prov_text", file=code(Path(m.get("text_file", "")).name)),
    }.get(m["source_type"], lambda: "")()
    cover = (c.t("cover_timed", cues=len(c.ir["cues"]), segs=len(c.segs)) if c.timed
             else c.t("cover_text", segs=len(c.segs)))
    tr = c.t("tr_done", lang=lang_name(c.tgt_lang)) if c.translated else c.t("tr_none")
    return {
        **ui_context(c.t, c.ui_lang),
        "page_title": title,
        "page_description": e.get("tagline") or title,
        "eyebrow": " · ".join(x for x in (src, m.get("uploader"), date) if x),
        "has_nav": bool(L.get("index")) or both,
        "nav_label": c.t("nav_label"),
        "index_href": L.get("index") or "",
        "nav_index": c.t("nav_index"),
        "page_links": [{"href": L[k], "label": c.t("nav_" + k), "current": "page" if k == current else "false"}
                       for k in ("transcript", "summary")] if both else [],
        "origin_href": "" if both else url,
        "origin_label": c.t("origin_link"),
        "content_lang": c.tgt_lang,
        "content_dir": "rtl" if is_rtl(c.tgt_lang) else "ltr",
        "title": title,
        "tagline": e.get("tagline") or "",
        "tokens": [{"label": c.t(k), "value": v, "badge": badge} for k, v, badge in tokens if v],
        "ctas": ctas,
        "prov_title": c.t("prov_title"),
        "_prov": [("prov_source", prov_src), ("prov_cover", esc(cover)), ("prov_translate", esc(tr))],
    }


def prov_rows(c: Ctx, base: dict, extra: str) -> list:
    rows = base.pop("_prov") + ([("prov_note", extra)] if extra else [])
    return [{"label": c.t(k), "value_html": v} for k, v in rows]


def topic_list(c: Ctx, href=None) -> list:
    return [{"num": n, "num_label": f"{n:02d}", "title": t["title"], "brief": t.get("brief") or "",
             "span": c.span(segs), "href": href(n) if href else "", "_t": t, "_segs": segs}
            for n, t, segs in c.topics()]


# ---------------------------------------------------------------- transcript page

def group_paragraphs(c: Ctx, segs: list, prev_end):
    """Yield ('gap', prev_end, seg) or ('para', [segs]); the same grouping is used for every mode.

    Paragraphs are only line breaks between whole segments, so no text is ever dropped. If you
    wrote `enrich.paragraphs` (segment ids that open a paragraph) those win; otherwise a reading-rhythm
    heuristic is used. Topic boundaries, caption gaps and enrich.speakers always break. A speaker
    change in the captions (seg["turn"]) is only a soft hint, never a rule on its own.
    """
    starts = c.para_starts
    cur = []
    for seg in segs:
        gap = c.timed and prev_end is not None and seg["start_ms"] - prev_end >= GAP_MS
        brk = not c.timed or gap or (cur and c.speaker[seg["id"]] != c.speaker[cur[-1]["id"]])
        if cur and not brk and starts is not None:
            brk = seg["id"] in starts
        elif cur and not brk and c.timed:
            units = sum(text_units(s["text"]) for s in cur)
            pause = seg["start_ms"] - prev_end
            brk = ((seg.get("turn") and units >= 120)                           # new speaker, enough said
                   or (pause >= 2500 and units >= 200)                           # a breath, then new thought
                   or (units >= 420 and ends_sentence(cur[-1]["text"]))          # long enough
                   or len(cur) >= 6)
        if cur and brk:
            yield "para", cur
            cur = []
        if gap:
            yield "gap", prev_end, seg
        cur.append(seg)
        prev_end = seg["end_ms"] if c.timed else None
    if cur:
        yield "para", cur


ROW = {"is_gap": False, "is_turn": False, "is_para": False}


def text_block(c: Ctx, group: list, side: str, mode: str, second: bool = False) -> dict:
    """`uid` (seg<id>-<side>-<mode>) is unique per rendered span, so review tools that build
    selectors from element ids (e.g. textcast-chat-axi) point straight at one segment and side."""
    lang = c.lang(side)
    sep = "" if is_cjk_lang(lang) else " "
    return {
        "cls": "txt " + ("cjk" if is_cjk_lang(lang) else "latin") + (" second" if second else ""),
        "lang": lang,
        "segs": [{"sep": sep if k else "", "id": s["id"], "uid": f"seg{s['id']}-{side}-{mode}",
                  "text": c.text(s, side),
                  "t": f"{c.ts(s['start_ms'])}–{c.ts(s['end_ms'])}" if c.timed else ""}
                 for k, s in enumerate(group)],
    }


def flow_rows(c: Ctx, segs: list, mode: str, prev_end) -> list:
    rows, last_speaker = [], None
    for item in group_paragraphs(c, segs, prev_end):
        if item[0] == "gap":
            prev, seg = item[1], item[2]
            gap = seg["start_ms"] - prev
            rows.append({**ROW, "is_gap": True, "gap_cls": "prominent" if gap >= BIG_GAP_MS else "",
                         "gap_note": c.enrich.get("gap_notes", {}).get(str(seg["id"])) or c.t("gap_default"),
                         "gap_from": c.ts(prev), "gap_to": c.ts(seg["start_ms"]),
                         "gap_span": c.t("gap_span", dur=fmt_dur(gap))})
            last_speaker = None
            continue
        group = item[1]
        who = c.speaker[group[0]["id"]]
        if who and who != last_speaker:
            rows.append({**ROW, "is_turn": True, "speaker": who, "color": c.colors[who]})
        last_speaker = who
        texts = ([text_block(c, group, "tgt", mode), text_block(c, group, "src", mode, second=True)] if mode == "bi"
                 else [text_block(c, group, mode, mode)])
        a = group[0]["start_ms"]
        rows.append({**ROW, "is_para": True, "texts": texts, "pnum": group[0]["id"] + 1,
                     "seek": a / 1000 if c.timed else "", "start": c.ts(a) if c.timed else "",
                     "end": c.ts(group[-1]["end_ms"]) if c.timed else "",
                     "play_title": c.t("play_from", t=c.ts(a)) if c.timed else ""})
    return rows


def render_transcript(ir: dict, enrich: dict, tr: dict, out_dir: Path, links: dict) -> str:
    c = Ctx(ir, enrich, tr, out_dir, links)
    ctx = page_context(c, "transcript")
    topics, prev_end = topic_list(c), (0 if c.timed else None)
    for tp in topics:
        tp["analysis"] = [{"text_html": md_inline(p)} for p in tp["_t"].get("analysis") or []]
        tp["flows"] = [{"mode": m, "rows": flow_rows(c, tp["_segs"], m, prev_end)} for m in c.modes]
        prev_end = tp["_segs"][-1]["end_ms"] if c.timed else None
    extra = ""
    if c.player:
        extra = esc(c.t("note_seek"))
        if c.player["kind"] == "youtube":
            extra += " " + esc(c.t("note_youtube", cmd="\0")).replace("\0", "<code>textcast.py serve</code>")
    mode_labels = {"src": f"{c.t('mode_src')} · {lang_name(c.src_lang)}",
                   "tgt": f"{c.t('mode_tgt')} · {lang_name(c.tgt_lang)}", "bi": c.t("mode_bi")}
    ctx.update({
        "body_class": " ".join([f"mode-{c.modes[0]}"] + (["has-player"] if c.player else []) + ([] if c.timed else ["textonly"])),
        "toc_title": c.t("toc_title"),
        "topics": topics,
        "count": c.t("count_timed" if c.timed else "count_text", topics=len(topics), n=len(c.segs)),
        "translated": c.translated,
        "mode_label": c.t("mode_label"),
        "modes": [{"mode": m, "label": mode_labels[m]} for m in ("src", "tgt", "bi")],
        "expand_all": c.t("expand_all"), "collapse_all": c.t("collapse_all"),
        "toggle_open": c.t("toggle_open"), "toggle_closed": c.t("toggle_closed"),
        "analysis_label": c.t("analysis"),
        "original_label": c.t("original_timed") if c.timed else c.t("original"),
        "gap_label": c.t("gap_label"),
        "timed": c.timed, "seekable": bool(c.player),
        "player": bool(c.player), "player_now": c.t("player_now"), "player_close": c.t("player_close"),
        "data_html": data_json({"modes": c.modes, "defaultMode": c.modes[0], "player": c.player,
                                "times": [[s["start_ms"] / 1000, s["end_ms"] / 1000] for s in c.segs] if c.timed else []}),
    })
    ctx["prov_rows"] = prov_rows(c, ctx, extra)
    return render("transcript.html", ctx)


# ---------------------------------------------------------------- summary page

def render_summary(ir: dict, enrich: dict, out_dir: Path, links: dict) -> str:
    c = Ctx(ir, enrich, {}, out_dir, links)
    sm = enrich["summary"]
    ctx = page_context(c, "summary")
    tlink = links.get("transcript")
    ctx.update({
        "body_class": "mode-src summary-page",
        "sum_one": c.t("sum_one"), "sum_points": c.t("sum_points"),
        "sum_dims": c.t("sum_dims"), "sum_outline": c.t("sum_outline"),
        "one_sentence_html": md_inline(sm["one_sentence"]),
        "points": [{"text_html": md_inline(p)} for p in sm.get("key_points") or []],
        "dims": [{"title": d.get("title") or "", "paragraphs": [{"text_html": md_inline(p)} for p in d.get("paragraphs") or []]}
                 for d in sm.get("dimensions") or []],
        "topics": topic_list(c, (lambda n: f"{tlink}#topic-{n}") if tlink else None),
        "data_html": data_json({"modes": ["src"], "defaultMode": "src", "player": None, "times": []}),
    })
    ctx["prov_rows"] = prov_rows(c, ctx, esc(c.t("note_summary")))
    return render("summary.html", ctx)
