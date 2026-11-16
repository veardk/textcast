"""Site layer: category folders, numbered page files, category.json manifests and index.html.

textcast/output/
├── index.html                 rebuilt on every publish
├── textcast.json              site settings ({"ui_lang": …})
├── .work/<slug>/              ir.json + source/ (ingest), <lang>/ per target language (ignored by the index)
└── <category>/                kebab-case folder, one per category
    ├── category.json          {"slug", "title", "description", "items": [...]}
    ├── 01-<slug>.html
    ├── 01-<slug>-summary.html
    └── 02-<slug>-<lang>.html  same source, a language other than the site's
"""
import re
from datetime import datetime
from pathlib import Path

from tc_common import fmt_dur, lang_name, read_json, same_lang, write_json
from tc_render import data_json, load_bundles, ui_context, ui_locale
from tc_template import render

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CATEGORY_FILE = "category.json"
SITE_FILE = "textcast.json"
NUM_RE = re.compile(r"^(\d+)-")


class SiteError(Exception):
    pass


def check_slug(value: str, what: str) -> str:
    if not SLUG_RE.fullmatch(value or ""):
        raise SiteError(f"{what} {value!r} must be kebab-case: lowercase letters/digits joined by single hyphens "
                        f"(e.g. ai-engineering, steve-jobs-stanford-speech)")
    return value


_SOURCE_PREFIX = ("youtube", "yt", "bilibili", "bili", "spotify", "video", "tmp", "temp")


def check_page_slug(value: str) -> str:
    """A page slug names the content (e.g. standard-agents-spec-talk), never the link it came from."""
    check_slug(value, "slug")
    parts = value.split("-")
    id_like = [p for p in parts if len(p) >= 8 and sum(c.isdigit() for c in p) >= 2 and any(c.isalpha() for c in p)]
    if parts[0] in _SOURCE_PREFIX or id_like or re.fullmatch(r"(bv|av)\d.*", parts[0]):
        raise SiteError(f"slug {value!r} looks like a source link, video ID or temporary name; name the page "
                        f"after its content in 3-6 English words (e.g. standard-agents-spec-talk) and pass "
                        f"--slug, or rename the work dir")
    return value


def scan_categories(root: Path) -> list[dict]:
    """Every non-hidden sub-folder with a category.json, newest activity first."""
    cats = []
    if not root.is_dir():
        return cats
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        man = read_json(d / CATEGORY_FILE)
        if man is None:
            continue
        man.setdefault("slug", d.name)
        man.setdefault("title", d.name.replace("-", " ").title())
        man["items"] = sorted(man.get("items") or [], key=lambda it: it["number"])
        man["_dir"] = d
        cats.append(man)
    cats.sort(key=lambda c: max([it.get("published", "") for it in c["items"]] or [""]), reverse=True)
    return cats


def next_number(cat_dir: Path, items: list[dict]) -> int:
    used = {it["number"] for it in items}
    used |= {int(m.group(1)) for f in cat_dir.glob("*.html") if (m := NUM_RE.match(f.name))}
    return max(used, default=0) + 1


def place(root: Path, category: str, slug: str, category_title: str | None, description: str | None):
    """Find or create the category folder and decide the item's number and file names.

    Re-publishing the same slug keeps its number; a new slug takes the next free number."""
    check_slug(category, "category")
    check_page_slug(slug)
    cat_dir = root / category
    created = not (cat_dir / CATEGORY_FILE).exists()
    cat_dir.mkdir(parents=True, exist_ok=True)
    man = read_json(cat_dir / CATEGORY_FILE) or {"slug": category, "items": []}
    if category_title:
        man["title"] = category_title
    man.setdefault("title", category.replace("-", " ").title())
    if description:
        man["description"] = description
    existing = next((it for it in man["items"] if it["slug"] == slug), None)
    number = existing["number"] if existing else next_number(cat_dir, man["items"])
    stem = f"{number:02d}-{slug}"
    elsewhere = [c["slug"] for c in scan_categories(root)
                 if c["slug"] != category and any(it["slug"] == slug for it in c["items"])]
    return {"dir": cat_dir, "manifest": man, "existing": existing, "number": number,
            "transcript": f"{stem}.html", "summary": f"{stem}-summary.html",
            "created": created, "elsewhere": elsewhere}


def record(slot: dict, slug: str, ir: dict, enrich: dict, ui_lang: str, files: dict, work: Path, root: Path) -> None:
    """Write the item into category.json and delete files a previous publish left behind."""
    man, meta = slot["manifest"], ir["meta"]
    old = slot["existing"] or {}
    for key in ("transcript", "summary"):
        stale = old.get(key)
        if stale and stale != files.get(key) and (slot["dir"] / stale).exists():
            (slot["dir"] / stale).unlink()
    item = {
        "number": slot["number"],
        "slug": slug,
        "title": enrich.get("title") or meta.get("title") or slug,
        "tagline": enrich.get("tagline") or "",
        "source_type": meta["source_type"],
        "source_url": meta.get("source_url") or "",
        "duration_ms": meta.get("duration_ms"),
        "source_lang": enrich["source_lang"],
        "target_lang": enrich["target_lang"],
        "ui_lang": ui_lang,
        "transcript": files.get("transcript"),
        "summary": files.get("summary"),
        "published": datetime.now().isoformat(timespec="seconds"),
        "work": Path(work).resolve().relative_to(root.resolve()).as_posix()
        if Path(work).resolve().is_relative_to(root.resolve()) else str(Path(work).resolve()),
    }
    man["items"] = sorted([it for it in man["items"] if it["slug"] != slug] + [item], key=lambda it: it["number"])
    write_json(slot["dir"] / CATEGORY_FILE, man)


# ---------------------------------------------------------------- index page

class UI:
    def __init__(self, ui_lang: str):
        bundles = load_bundles()
        locale = ui_locale(ui_lang, bundles)
        self.ui_lang = ui_lang if locale != "en" or ui_lang.lower().startswith("en") else "en"
        self.s = {**bundles["en"], **bundles[locale]}

    def t(self, key: str, **kw) -> str:
        return self.s[key].format(**kw) if kw else self.s[key]


def site_settings(root: Path, ui_lang: str | None = None) -> dict:
    """textcast.json; the first publish (or --ui-lang) fixes the index page language."""
    cfg = read_json(root / SITE_FILE, {}) or {}
    if ui_lang and cfg.get("ui_lang") != ui_lang:
        cfg["ui_lang"] = ui_lang
        write_json(root / SITE_FILE, cfg)
    return cfg


def _item(ui: UI, cat_slug: str, it: dict) -> dict:
    href = lambda f: f"{cat_slug}/{f}"  # noqa: E731
    langs = (f'{lang_name(it["source_lang"])} → {lang_name(it["target_lang"])}'
             if not same_lang(it.get("source_lang"), it.get("target_lang")) else lang_name(it.get("source_lang")))
    return {
        "href": href(it.get("transcript") or it.get("summary")),
        "num_label": f'{it["number"]:02d}',
        "lang": it.get("target_lang") or "",
        "title": it["title"],
        "tagline": it.get("tagline") or "",
        "source": ui.s.get(f"src_{it['source_type']}", it["source_type"]),
        "duration": fmt_dur(it["duration_ms"]) if it.get("duration_ms") else "",
        "langs": langs,
        "links": [{"href": href(it[k]), "label": ui.t("nav_" + k)} for k in ("transcript", "summary") if it.get(k)],
    }


def render_index(root: Path, ui_lang: str) -> str:
    ui = UI(ui_lang)
    cats = []
    for c in scan_categories(root):
        # skip entries whose files were removed by hand
        c["items"] = [it for it in c["items"] if any((c["_dir"] / it[k]).exists() for k in ("transcript", "summary") if it.get(k))]
        if c["items"]:
            cats.append(c)
    return render("index.html", {
        **ui_context(ui.t, ui.ui_lang),
        "tagline": ui.t("idx_tagline"),
        "stats": ui.t("idx_stats", cats=len(cats), pages=sum(len(c["items"]) for c in cats)),
        "categories": [{"slug": c["slug"], "title": c["title"],
                        "count": ui.t("idx_items", n=len(c["items"])), "description": c.get("description") or "",
                        "items": [_item(ui, c["slug"], it) for it in c["items"]]}
                       for c in cats],
        "empty": ui.t("idx_empty"),
        "data_html": data_json({"modes": ["src"], "player": None, "times": []}),
    })


def write_index(root: Path, ui_lang: str | None = None) -> Path:
    cfg = site_settings(root, ui_lang)
    out = root / "index.html"
    out.write_text(render_index(root, cfg.get("ui_lang") or "en"), encoding="utf-8")
    return out
