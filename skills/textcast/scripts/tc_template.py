"""Tiny template engine for templates/*.html.

Templates are complete, previewable HTML files. Syntax:

  {{name}} / {{name|sample}}             value, HTML-escaped (names ending in _html are inserted raw).
                                         The sample text is what a browser shows when the template
                                         itself is opened (templates/preview.js swaps it in).
  <!-- @each name --> … <!-- @end name -->  repeat for every item of a list; item keys shadow outer keys.
  <!-- @if name --> … <!-- @end name -->    keep when truthy; `@if !name` keeps when falsy.
  <!-- @sample --> … <!-- @end sample -->   preview-only filler, removed when rendering.

<link rel="stylesheet" href="x.css"> and <script src="x.js"></script> pointing at files in templates/
are inlined, so every generated page is a single self-contained file; preview.js is dropped. The
content of <script id="textcast-data"> is replaced with the page's JSON data.
"""
import html
import re
from collections import ChainMap
from pathlib import Path

TPL = Path(__file__).resolve().parent.parent / "templates"

_SAMPLE = re.compile(r"<!--\s*@sample\s*-->.*?<!--\s*@end\s+sample\s*-->", re.S)
_DATA = re.compile(r'(<script id="textcast-data" type="application/json">).*?(</script>)', re.S)
_CSS = re.compile(r'<link rel="stylesheet" href="([\w.-]+\.css)">')
_JS = re.compile(r'<script src="([\w.-]+\.js)"></script>')
_TOKEN = re.compile(r"<!--\s*@(each|if|end)\s+(!?)([\w-]+)\s*-->|\{\{(\w+)(?:\|.*?)?\}\}", re.S)
_ASSET = "\x00asset:{}\x00"

_cache: dict[str, list] = {}


class TemplateError(Exception):
    pass


def _parse(src: str, name: str) -> list:
    root: list = []
    stack = [("root", "", root)]
    pos = 0
    for m in _TOKEN.finditer(src):
        stack[-1][2].append(("text", src[pos:m.start()]))
        pos = m.end()
        kind, neg, block, var = m.groups()
        if var:
            stack[-1][2].append(("var", var))
        elif kind == "end":
            if stack[-1][1] != block:
                raise TemplateError(f"{name}: '@end {block}' does not close '@{stack[-1][0]} {stack[-1][1]}'")
            stack.pop()
        else:
            children: list = []
            stack[-1][2].append((kind, block, bool(neg), children))
            stack.append((kind, block, children))
    if len(stack) > 1:
        raise TemplateError(f"{name}: '@{stack[-1][0]} {stack[-1][1]}' is never closed")
    root.append(("text", src[pos:]))
    return root


def _compile(name: str) -> list:
    if name not in _cache:
        src = (TPL / name).read_text(encoding="utf-8")
        src = _SAMPLE.sub("", src).replace(' data-preview="hide"', "")
        src = _DATA.sub(lambda m: m.group(1) + "{{data_html}}" + m.group(2), src)
        src = _CSS.sub(lambda m: _ASSET.format(m.group(1)), src)
        src = _JS.sub(lambda m: "" if m.group(1) == "preview.js" else _ASSET.format(m.group(1)), src)
        _cache[name] = _parse(src, name)
    return _cache[name]


def _lookup(ctx: ChainMap, key: str):
    try:
        return ctx[key]
    except KeyError:
        raise TemplateError(f"template value '{key}' was not provided") from None


def _render(nodes: list, ctx: ChainMap, out: list) -> None:
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(node[1])
        elif kind == "var":
            value = _lookup(ctx, node[1])
            value = "" if value is None else str(value)
            out.append(value if node[1].endswith("_html") else html.escape(value, quote=True))
        elif kind == "if":
            if bool(_lookup(ctx, node[1])) != node[2]:
                _render(node[3], ctx, out)
        else:  # each
            for item in _lookup(ctx, node[1]) or []:
                _render(node[3], ctx.new_child(item if isinstance(item, dict) else {"item": item}), out)


def _asset(name: str) -> str:
    body = (TPL / name).read_text(encoding="utf-8")
    return f"<style>\n{body}\n</style>" if name.endswith(".css") else f"<script>\n{body}\n</script>"


def render(name: str, context: dict) -> str:
    out: list = []
    _render(_compile(name), ChainMap(context), out)
    page = "".join(out)
    return re.sub("\x00asset:([\\w.-]+)\x00", lambda m: _asset(m.group(1)), page)
