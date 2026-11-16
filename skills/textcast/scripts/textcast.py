#!/usr/bin/env python3
"""
textcast.py — Ingest → IR → (Enrich by the executing model) → Render.

  ingest <url|file> -o textcast/output/.work/<slug>
                                 Build ir.json (cues + reading segments).
  <work> below is the language folder textcast/output/.work/<slug>/<lang> (e.g. …/zh-CN).
  show   <work> [--from N --count K | --untranslated | --topics]
                                 Print segments compactly for you to read.
  audit  <work> [--mode …]      Check enrich.json + translations against the IR.
  render <work> [--mode …]      Preview pages inside the work dir.
  categories [textcast/output]  List category folders and their pages.
  publish <work> --category <kebab> [--category-title …] [--mode transcript|summary|both]
                                 Write textcast/output/<category>/NN-<slug>.html, update category.json,
                                 rebuild textcast/output/index.html.
  index  [textcast/output] [--ui-lang …]
                                 Rebuild the index page.
  clean  [textcast/output] [--delete]
                                 List (or delete) unpublished work dirs and leftover files.
  serve  [dir] [--port 8765]    Serve over http (YouTube embeds need it).

You author <work>/enrich.json and <work>/translations/*.json; see
references/ir-schema.md.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tc_common import (ENRICH_FILE, IR_FILE, LOCK_FILE, TRANSLATIONS_DIR, fmt_dur, fmt_ts, ir_fingerprint,  # noqa: E402
                       lang_name, load_translations, norm_lang, read_json, same_lang, text_units,
                       write_json)
from tc_sources import IngestError, ingest  # noqa: E402


def load(work: Path) -> tuple[dict, dict, dict]:
    """work is the language folder <slug>/<lang>; ir.json lives one level up, shared by all languages."""
    if (work / IR_FILE).exists():
        sys.exit(f"{work} is the source folder; pass its language folder instead, "
                 f"e.g. {work}/zh-CN (put enrich.json there)")
    ir = read_json(work.parent / IR_FILE)
    if ir is None:
        sys.exit(f"{work.parent / IR_FILE} not found — run ingest first "
                 f"(ingest writes textcast/output/.work/<slug>/, languages go in textcast/output/.work/<slug>/<lang>/)")
    enrich = read_json(work / ENRICH_FILE, {})
    for key in ("source_lang", "target_lang"):
        if enrich.get(key):
            enrich[key] = norm_lang(enrich[key])
    if enrich.get("target_lang") and enrich["target_lang"] != work.name:
        sys.exit(f"{work} holds target_lang {enrich['target_lang']!r}; the folder must be named after it: "
                 f"{work.parent / enrich['target_lang']}")
    if work.is_dir():
        fp, lock = ir_fingerprint(ir), work / LOCK_FILE
        if not lock.exists():
            lock.write_text(fp + "\n", encoding="utf-8")
        elif lock.read_text(encoding="utf-8").strip() != fp:
            sys.exit(f"{work.parent / IR_FILE} changed after this language was started (re-ingested?), so its "
                     f"segment ids no longer match {work}/translations. Restore the old ir.json, or delete "
                     f"{work} and translate again.")
    try:
        tr = load_translations(work, enrich)
    except ValueError as e:
        sys.exit(str(e))
    return ir, enrich, tr


def language_dirs(base: Path) -> list[Path]:
    return [d for d in sorted(base.iterdir()) if d.is_dir() and d.name not in ("source", TRANSLATIONS_DIR)] if base.is_dir() else []


def needs_translation(enrich: dict) -> bool:
    return bool(enrich.get("target_lang")) and not same_lang(enrich.get("source_lang"), enrich["target_lang"])


def topic_ranges(enrich: dict, n_segs: int) -> list[tuple[dict, int, int]]:
    """Each topic owns segments [from_seg, next.from_seg) — contiguous by construction."""
    topics = enrich.get("topics") or []
    out = []
    for k, t in enumerate(topics):
        end = topics[k + 1]["from_seg"] if k + 1 < len(topics) else n_segs
        out.append((t, t["from_seg"], end))
    return out


# ---------------------------------------------------------------- audit

def audit(ir: dict, enrich: dict, tr: dict, mode: str) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    cues, segs = ir["cues"], ir["segments"]
    n = len(segs)

    # IR integrity: every cue in exactly one segment, in order
    expect = 0
    for s in segs:
        a, b = s["cues"]
        if a != expect or b < a:
            errs.append(f"IR: segment #{s['id']} covers cues {a}-{b}, expected to start at {expect}")
        expect = b + 1
    if expect != len(cues):
        errs.append(f"IR: segments cover {expect} of {len(cues)} cues")

    if not enrich:
        return errs + [f"{ENRICH_FILE} missing"], warns
    for key in ("source_lang", "target_lang"):
        if not enrich.get(key):
            errs.append(f"enrich.{key} is required")

    topics = enrich.get("topics") or []
    if not topics:
        errs.append("enrich.topics is empty")
    prev = -1
    for k, t in enumerate(topics):
        fs = t.get("from_seg")
        if not isinstance(fs, int) or not 0 <= fs < n:
            errs.append(f"topic {k + 1}: from_seg {fs!r} out of range 0..{n - 1}")
            continue
        if k == 0 and fs != 0:
            errs.append("topic 1 must start at from_seg 0 (no dialogue may precede the first topic)")
        if fs <= prev:
            errs.append(f"topic {k + 1}: from_seg {fs} must be greater than previous {prev} (chronological, non-overlapping)")
        prev = fs
        if not t.get("title"):
            errs.append(f"topic {k + 1}: missing title")
        if not t.get("analysis"):
            errs.append(f"topic {k + 1}: missing analysis paragraphs")
        if not t.get("brief"):
            warns.append(f"topic {k + 1}: missing brief")

    prev = -1
    for sp in enrich.get("speakers") or []:
        if not isinstance(sp.get("from_seg"), int) or sp["from_seg"] <= prev or sp["from_seg"] >= n:
            errs.append(f"speakers: from_seg {sp.get('from_seg')!r} must be increasing and < {n}")
        else:
            prev = sp["from_seg"]

    prev = -1
    for i in enrich.get("paragraphs") or []:
        if not isinstance(i, int) or i <= prev or i >= n:
            errs.append(f"paragraphs: {i!r} must be an integer segment id, increasing and < {n}")
            break
        prev = i

    if needs_translation(enrich):
        missing = [s["id"] for s in segs if not str(tr.get(str(s["id"]), "")).strip()]
        if missing:
            errs.append(f"translations: {len(missing)}/{n} segments untranslated, first ids: {missing[:12]}")
        extra = [k for k in tr if not k.isdigit() or int(k) >= n]
        if extra:
            errs.append(f"translations: unknown segment ids {extra[:12]}")

    if mode in ("summary", "both"):
        sm = enrich.get("summary") or {}
        for key in ("one_sentence", "key_points"):
            if not sm.get(key):
                errs.append(f"summary.{key} is required for summary mode")
        if not sm.get("dimensions"):
            warns.append("summary.dimensions is empty")
    return errs, warns


# ---------------------------------------------------------------- commands

def cmd_ingest(a) -> int:
    work = Path(a.output)
    old = read_json(work / IR_FILE)
    started = [d.name for d in language_dirs(work) if (d / LOCK_FILE).exists()]
    if old and started and not a.force:
        print(f"ingest refused: {work} already has languages in progress ({', '.join(started)}). Re-ingesting "
              f"can renumber segments and orphan their translations. Use a new folder, or --force if the "
              f"translations may be redone.", file=sys.stderr)
        return 1
    try:
        ir = ingest(a.source, work, sub_lang=a.sub_lang, media=a.media, title=a.title)
    except IngestError as e:
        print(f"ingest failed: {e}", file=sys.stderr)
        return 1
    write_json(work / IR_FILE, ir)
    if old and started and ir_fingerprint(ir) != ir_fingerprint(old):
        print(f"  warn: segments changed; existing languages ({', '.join(started)}) must be translated again")
    m = ir["meta"]
    dur = fmt_dur(m["duration_ms"]) if m.get("duration_ms") else "—"
    print(f"Wrote {work / IR_FILE}")
    print(f"  title: {m['title']}\n  source: {m['source_type']} · subtitles: {m['subtitle_kind']} · duration: {dur}" + (f" · via {m['fetcher']}" if m.get('fetcher') else ""))
    print(f"  cues: {len(ir['cues'])} → segments: {len(ir['segments'])} · timestamps: {m['has_timestamps']}"
          f" · language guess: {m['source_lang_guess']}")
    return 0


def cmd_show(a) -> int:
    work = Path(a.work)
    ir, enrich, tr = load(work)
    segs = ir["segments"]
    long = (ir["meta"].get("duration_ms") or 0) >= 3600_000
    if a.topics:
        for k, (t, s, e) in enumerate(topic_ranges(enrich, len(segs))):
            span = f"{fmt_ts(segs[s]['start_ms'], long)}–{fmt_ts(segs[e - 1]['end_ms'], long)}" if ir["meta"]["has_timestamps"] else ""
            print(f"{k + 1:02d} #{s}-#{e - 1} {span} {t.get('title', '')}")
        return 0
    if a.untranslated:
        if not needs_translation(enrich):
            print("No translation needed (set enrich.source_lang/target_lang first, or they are the same).")
            return 0
        todo = [s for s in segs if not str(tr.get(str(s["id"]), "")).strip()]
        pick, units = [], 0
        for s in todo[: a.count or len(todo)]:
            if pick and units + text_units(s["text"]) > a.max_units:
                break
            pick.append(s)
            units += text_units(s["text"])
        print(f"# {len(todo)} untranslated; showing {len(pick)}")
    else:
        pick = segs[a.start: a.start + a.count]
        print(f"# segments {a.start}-{a.start + len(pick) - 1} of {len(segs)}")
    if any(s.get("turn") for s in pick):
        print("# » = speaker change in the source captions (not part of the text)")
    for s in pick:
        ts = f"[{fmt_ts(s['start_ms'], long)}] " if s["start_ms"] is not None else ""
        print(f"#{s['id']} {ts}{'» ' if s.get('turn') else ''}{s['text']}")
    return 0


def cmd_audit(a) -> int:
    ir, enrich, tr = load(Path(a.work))
    errs, warns = audit(ir, enrich, tr, a.mode)
    n = len(ir["segments"])
    done = sum(1 for s in ir["segments"] if str(tr.get(str(s["id"]), "")).strip())
    print(f"segments: {n} · topics: {len(enrich.get('topics') or [])} · translated: {done}/{n}"
          f" · {lang_name(enrich.get('source_lang'))} → {lang_name(enrich.get('target_lang'))}")
    for w in warns:
        print(f"  warn: {w}")
    for e in errs:
        print(f"  ERROR: {e}")
    print("audit passed" if not errs else f"audit failed ({len(errs)} error(s))")
    return 1 if errs else 0


def checked(work: Path, mode: str):
    """Load a work dir and run the audit; None when render/publish must refuse."""
    ir, enrich, tr = load(work)
    errs, warns = audit(ir, enrich, tr, mode)
    for w in warns:
        print(f"  warn: {w}")
    if errs:
        for e in errs:
            print(f"  ERROR: {e}", file=sys.stderr)
        print("refused: fix audit errors first", file=sys.stderr)
        return None
    return ir, enrich, tr


def write_pages(ir, enrich, tr, out_dir: Path, mode: str, names: dict, index: str | None) -> dict:
    """Render the requested pages into out_dir; returns {"transcript": file|None, "summary": file|None}."""
    from tc_render import render_summary, render_transcript

    files = {"transcript": names["transcript"] if mode in ("transcript", "both") else None,
             "summary": names["summary"] if mode in ("summary", "both") else None}
    links = {**files, "index": index}
    if files["transcript"]:
        (out_dir / files["transcript"]).write_text(render_transcript(ir, enrich, tr, out_dir, links), encoding="utf-8")
    if files["summary"]:
        (out_dir / files["summary"]).write_text(render_summary(ir, enrich, out_dir, links), encoding="utf-8")
    for f in files.values():
        if f:
            print(f"Wrote {out_dir / f}")
    return files


def cmd_render(a) -> int:
    """Preview inside the work dir (transcript.html / summary.html), not part of the site."""
    work = Path(a.work)
    data = checked(work, a.mode)
    if data is None:
        return 1
    write_pages(*data, work, a.mode, {"transcript": "transcript.html", "summary": "summary.html"}, index=None)
    return 0


def cmd_categories(a) -> int:
    from tc_site import scan_categories

    root = Path(a.root)
    cats = scan_categories(root)
    if not cats:
        print(f"No categories under {root} yet — publish with a new kebab-case --category to create one.")
        return 0
    for c in cats:
        desc = f" — {c['description']}" if c.get("description") else ""
        print(f"{c['slug']}  「{c['title']}」 {len(c['items'])} page(s){desc}")
        for it in c["items"]:
            print(f"    {it['number']:02d}  {it['slug']}  {it['title']}")
    return 0


def cmd_publish(a) -> int:
    from tc_render import Ctx
    from tc_site import SiteError, place, record, site_settings, write_index

    work, root = Path(a.work), Path(a.root)
    data = checked(work, a.mode)
    if data is None:
        return 1
    ir, enrich, tr = data
    from tc_site import site_settings as _site
    slug = a.slug or work.resolve().parent.name
    site_lang = _site(root).get("ui_lang") or enrich.get("ui_lang") or enrich["target_lang"]
    if not a.slug and not same_lang(enrich["target_lang"], site_lang):
        slug = f"{slug}-{enrich['target_lang'].lower()}"  # second language of the same source: its own page
    try:
        slot = place(root, a.category, slug, a.category_title, a.category_desc)
    except SiteError as e:
        print(f"publish failed: {e}", file=sys.stderr)
        return 1
    if slot["created"]:
        print(f"Created category {slot['dir']}/")
    if slot["elsewhere"]:
        print(f"  note: '{slug}' is also published in: {', '.join(slot['elsewhere'])}")
    files = write_pages(ir, enrich, tr, slot["dir"], a.mode, slot, index="../index.html")
    ui_lang = Ctx(ir, enrich, tr, slot["dir"], {}).ui_lang
    record(slot, slug, ir, enrich, ui_lang, files, work, root)
    cfg = site_settings(root)
    print(f"Wrote {write_index(root, None if cfg.get('ui_lang') else ui_lang)}")
    return 0


def cmd_index(a) -> int:
    from tc_site import write_index

    print(f"Wrote {write_index(Path(a.root), a.ui_lang)}")
    return 0


def cmd_clean(a) -> int:
    """Unpublished work dirs and leftovers under textcast/output/.work. Lists by default; --delete removes them."""
    import shutil
    import time
    from tc_site import scan_categories

    root = Path(a.root)
    wroot = root / ".work"
    published = set()
    for c in scan_categories(root):
        for it in c["items"]:
            if it.get("work") and any((c["_dir"] / it[k]).exists() for k in ("transcript", "summary") if it.get(k)):
                published.add((root / it["work"]).resolve())
    found = []  # (path, reason)
    for base in sorted(wroot.iterdir()) if wroot.is_dir() else []:
        if not base.is_dir():
            continue
        if base.name.startswith("_new-"):
            found.append((base, "temporary ingest folder that was never renamed"))
            continue
        if not (base / IR_FILE).exists():
            found.append((base, "no ir.json"))
            continue
        langs = language_dirs(base)
        live = [d for d in langs if d.resolve() in published]
        if not live:
            found.append((base, "never published" + (f" (languages: {', '.join(d.name for d in langs)})" if langs else "")))
            continue
        for d in langs:
            if d not in live:
                found.append((d, "language never published"))
            else:
                found += [(d / f, "render preview") for f in ("transcript.html", "summary.html") if (d / f).exists()]
    found += [(f, "Finder file") for f in wroot.rglob(".DS_Store")] if wroot.is_dir() else []
    if not found:
        print("Nothing to clean.")
        return 0
    now = time.time()
    for path, why in found:
        age = (now - path.stat().st_mtime) / 3600
        print(f"{'deleted' if a.delete else 'would delete'}  {path}  — {why}, modified {age:.1f} h ago")
        if a.delete:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    if not a.delete:
        print("Nothing removed. Re-run with --delete once the user confirms (a recent folder may be another session's work in progress).")
    return 0


def cmd_serve(a) -> int:
    import functools
    import http.server

    base = Path(a.dir).resolve()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(base))
    with http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler) as httpd:
        page = next((p for p in ("index.html", "transcript.html", "summary.html") if (base / p).exists()), "")
        print(f"Serving {base} at http://127.0.0.1:{a.port}/{page}  (Ctrl+C to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="build ir.json from a URL or file")
    s.add_argument("source")
    s.add_argument("-o", "--output", required=True, help="source folder, e.g. textcast/output/.work/<slug> (languages go in <slug>/<lang>/)")
    s.add_argument("--sub-lang", help="force a subtitle track language (online sources)")
    s.add_argument("--media", help="local audio/video file paired with a subtitle file, enables click-to-seek")
    s.add_argument("--title", help="override the title")
    s.add_argument("--force", action="store_true", help="re-ingest even though languages are in progress")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("show", help="print segments for reading/translating")
    s.add_argument("work")
    s.add_argument("--from", dest="start", type=int, default=0)
    s.add_argument("--count", type=int, default=120, help="segments to print (with --untranslated: an upper bound, 0 = none)")
    s.add_argument("--untranslated", action="store_true",
                   help="list the next batch of untranslated segments, sized by --max-units")
    s.add_argument("--max-units", type=int, default=12000,
                   help="--untranslated batch size in reading units (CJK char = 3), default 12000")
    s.add_argument("--topics", action="store_true", help="print the topic outline with resolved ranges")
    s.set_defaults(fn=cmd_show)

    for name, fn, hlp in (("audit", cmd_audit, "check enrich.json + translations"),
                          ("render", cmd_render, "preview pages inside the work dir")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("work")
        s.add_argument("--mode", choices=("transcript", "summary", "both"), default="transcript")
        s.set_defaults(fn=fn)

    s = sub.add_parser("categories", help="list existing category folders (pick one before publishing)")
    s.add_argument("root", nargs="?", default="textcast/output")
    s.set_defaults(fn=cmd_categories)

    s = sub.add_parser("publish", help="render into textcast/output/<category>/NN-<slug>.html and rebuild index.html")
    s.add_argument("work")
    s.add_argument("--category", required=True, help="kebab-case folder; created if it does not exist")
    s.add_argument("--category-title", help="display name (set when creating a category, or to rename it)")
    s.add_argument("--category-desc", help="one-line description shown on the index card")
    s.add_argument("--slug", help="kebab-case page name (default: the source folder name, plus -<lang> "
                                  "when the language differs from the site language)")
    s.add_argument("--mode", choices=("transcript", "summary", "both"), default="transcript")
    s.add_argument("--root", default="textcast/output", help="site root (default: textcast/output)")
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("index", help="rebuild textcast/output/index.html")
    s.add_argument("root", nargs="?", default="textcast/output")
    s.add_argument("--ui-lang", help="index page language (saved in textcast.json)")
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("clean", help="list (or --delete) unpublished work dirs and leftover files")
    s.add_argument("root", nargs="?", default="textcast/output")
    s.add_argument("--delete", action="store_true")
    s.set_defaults(fn=cmd_clean)

    s = sub.add_parser("serve", help="serve a folder over http (needed for YouTube embeds)")
    s.add_argument("dir", nargs="?", default="textcast/output")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=cmd_serve)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
