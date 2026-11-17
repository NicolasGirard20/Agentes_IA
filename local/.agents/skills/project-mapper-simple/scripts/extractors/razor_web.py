"""Extractor for Razor (.cshtml) and HTML (.html/.htm) views."""

import html
import re
from typing import Any, Dict, List

from . import clip_text, compact_symbol, dedupe_keep_order


class RazorSymbolExtractor:
    """Extract models, layouts, titles, headings, partials, scripts, endpoints, and inline JS from Razor/HTML."""

    RAZOR_COMMENT_RE = re.compile(r"@\*([\s\S]{1,400}?)\*@")
    MODEL_RE = re.compile(r"^\s*@model\s+([^\r\n]+)", re.MULTILINE)
    USING_RE = re.compile(r"^\s*@using\s+([A-Za-z_][\w.]*)", re.MULTILINE)
    LAYOUT_RE = re.compile(r"""Layout\s*=\s*["']([^"']+)["']""")
    TITLE_RE = re.compile(r"""ViewBag\.Title\s*=\s*["']([^"']+)["']|<title[^>]*>([^<]+)</title>""", re.IGNORECASE)
    HEADING_RE = re.compile(r"<h[1-3][^>]*>([\s\S]{1,160}?)</h[1-3]>", re.IGNORECASE)
    PARTIAL_RE = re.compile(
        r"""@?(?:Html\.(?:Partial|RenderPartial|PartialAsync)|await\s+Html\.PartialAsync)\s*\(\s*["']([^"']+)["']"""
    )
    URL_ACTION_RE = re.compile(
        r"""(?:Url\.Action|Html\.(?:Action|BeginForm))\s*\(\s*["']([^"']+)["'](?:\s*,\s*["']([^"']+)["'])?"""
    )
    SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
    AJAX_URL_RE = re.compile(
        r"""(?:url\s*:|fetch\s*\(|\$\.(?:get|post)\s*\()\s*["'`]([^"'`\s)]+)["'`]""",
        re.IGNORECASE,
    )
    JS_FUNC_RE = re.compile(
        r"^[ \t]*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)\n]{0,100})\)",
        re.MULTILINE,
    )
    SECTION_RE = re.compile(r"@section\s+([A-Za-z_]\w*)", re.IGNORECASE)

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    @staticmethod
    def _strip_tags(raw: str) -> str:
        text = re.sub(r"@[\w.()]+|<[^>]+>", " ", raw)
        return clip_text(html.unescape(text), 100)

    def extract(self) -> Dict[str, Any]:
        models = dedupe_keep_order(self.MODEL_RE.findall(self.content), limit=3)
        usings = dedupe_keep_order(self.USING_RE.findall(self.content), limit=12)
        layouts = dedupe_keep_order(self.LAYOUT_RE.findall(self.content), limit=3)
        partials = dedupe_keep_order(self.PARTIAL_RE.findall(self.content), limit=12)
        scripts = dedupe_keep_order(self.SCRIPT_SRC_RE.findall(self.content), limit=15)
        sections = dedupe_keep_order(self.SECTION_RE.findall(self.content), limit=8)

        title = ""
        for g1, g2 in self.TITLE_RE.findall(self.content):
            candidate = html.unescape((g1 or g2).strip())
            if candidate:
                title = clip_text(candidate, 120)
                break

        headings = dedupe_keep_order(
            [self._strip_tags(h) for h in self.HEADING_RE.findall(self.content)],
            limit=5,
        )
        if not title and headings:
            title = headings[0]

        actions: List[str] = []
        target_controllers: List[str] = []
        for act, ctrl in self.URL_ACTION_RE.findall(self.content):
            if ctrl:
                actions.append(f"{ctrl}/{act}")
                target_controllers.append(ctrl)
            else:
                actions.append(act)
        actions = dedupe_keep_order(actions, limit=12)

        ajax_urls = dedupe_keep_order(
            [
                u
                for u in self.AJAX_URL_RE.findall(self.content)
                if not u.startswith(("@Url.", "@Html.", "@("))
            ],
            limit=10,
        )
        js_functions: List[Dict[str, Any]] = []
        for match in self.JS_FUNC_RE.finditer(self.content):
            name = match.group(1)
            line_no = self.content[: match.start()].count("\n") + 1
            args = [a.strip() for a in match.group(2).split(",") if a.strip()][:5]
            js_functions.append(
                compact_symbol({"name": name, "line": line_no, "args": args}, self.include_lines)
            )

        comment_match = self.RAZOR_COMMENT_RE.search(self.content[:1200])
        header_doc = clip_text(comment_match.group(1), 220) if comment_match else ""

        imports = dedupe_keep_order(usings + layouts + partials + scripts)
        notes: List[str] = []
        if models:
            notes.append("Modelo (@model): " + ", ".join(models))
        if headings:
            notes.append("Encabezados UI: " + " / ".join(headings[:4]))
        if partials:
            notes.append("Vistas parciales: " + ", ".join(partials[:6]))
        if actions or ajax_urls:
            notes.append("Acciones/Endpoints: " + ", ".join(dedupe_keep_order(actions + ajax_urls, limit=8)))
        if sections:
            notes.append("Secciones Razor: " + ", ".join(sections))

        model_refs = [m.split(".")[-1].rstrip(">").split("<")[-1] for m in models]
        references = dedupe_keep_order(layouts + partials + scripts + target_controllers + model_refs)
        keywords = dedupe_keep_order(
            ([title] if title else []) + headings + model_refs + partials + actions + ajax_urls,
            limit=20,
        )

        return {
            "imports": imports,
            "classes": [],
            "functions": js_functions,
            "exports": dedupe_keep_order(sections + [f["name"] for f in js_functions]),
            "title": title,
            "header_doc": header_doc,
            "references": references,
            "context_notes": notes,
            "keywords": keywords,
        }
