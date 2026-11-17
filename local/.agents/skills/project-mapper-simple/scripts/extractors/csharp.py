"""Lightweight, dependency-free C# (.cs) structural and context extractor."""

import re
from typing import Any, Dict, List

from . import clip_text, compact_symbol, dedupe_keep_order, extract_header_comment


class CSharpSymbolExtractor:
    """Extract namespaces, usings, types, attributes, XML summaries, and methods from C# files."""

    USING_RE = re.compile(r"^\s*using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;", re.MULTILINE)
    NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)", re.MULTILINE)
    TYPE_RE = re.compile(
        r"^(?P<indent>[ \t]*)(?:(?:public|internal|protected|private|static|abstract|sealed|partial)\s+)*"
        r"(?P<kind>class|interface|enum|struct|record)\s+(?P<name>[A-Za-z_]\w*)(?:<[^>\n]+>)?"
        r"(?:\s*:\s*(?P<bases>[^{\n]+))?",
        re.MULTILINE,
    )
    METHOD_RE = re.compile(
        r"^(?P<indent>[ \t]+)(?P<mods>(?:(?:public|protected|private|internal|static|virtual|override|async|new|sealed)\s+)+)"
        r"(?P<ret>[A-Za-z_][\w<>,.\[\]? ]*?)\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)\n]{0,220})\)\s*(?:\{|=>)",
        re.MULTILINE,
    )
    ATTR_LINE_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
    ROUTE_STRING_RE = re.compile(
        r"""\[(?:Route|RoutePrefix|Table|HttpGet|HttpPost|HttpPut|HttpDelete)\s*\(\s*["']([^"']+)["']""",
        re.IGNORECASE,
    )
    # Match project-style type references (instantiations, fields, return/param types)
    LOCAL_TYPE_REF_RE = re.compile(
        r"\b([A-Z][A-Za-z0-9_]*(?:DAO|Service|Controller|ViewModel|Context|Entities|Helper|Filter|Attribute|Repository))\b"
    )
    DBSET_RE = re.compile(r"\bDbSet<([A-Za-z_]\w*)>")

    SKIP_KEYWORDS = {"if", "for", "foreach", "while", "switch", "catch", "using", "lock", "return", "new"}

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.lines = content.splitlines()
        self.include_lines = include_lines

    def _preceding_xml_summary_and_attrs(self, line_idx: int) -> tuple[str, List[str]]:
        """Scan upwards from a declaration line (0-based) for XML <summary> and [Attributes]."""
        attrs: List[str] = []
        xml_lines: List[str] = []
        in_summary = False

        idx = line_idx - 1
        steps = 0
        while idx >= 0 and steps < 25:
            raw = self.lines[idx].strip()
            steps += 1
            if not raw:
                if xml_lines:
                    break
                idx -= 1
                continue
            if raw.startswith("[") and raw.endswith("]"):
                inner = raw[1:-1].strip()
                if inner and not inner.startswith("System.Diagnostics"):
                    attrs.append(inner)
                idx -= 1
                continue
            if raw.startswith("///"):
                text = raw[3:].strip()
                if "</summary>" in text:
                    in_summary = True
                    cleaned = re.sub(r"</?summary>", "", text).strip()
                    if cleaned:
                        xml_lines.append(cleaned)
                    if "<summary>" in text:
                        break
                    idx -= 1
                    continue
                if "<summary>" in text:
                    cleaned = re.sub(r"</?summary>", "", text).strip()
                    if cleaned:
                        xml_lines.append(cleaned)
                    break
                if in_summary:
                    cleaned = re.sub(r"<[^>]+>", "", text).strip()
                    if cleaned:
                        xml_lines.append(cleaned)
                    idx -= 1
                    continue
                # Fallback single-line /// comment without tags
                cleaned = re.sub(r"<[^>]+>", "", text).strip()
                if cleaned:
                    xml_lines.append(cleaned)
                idx -= 1
                continue
            break

        attrs.reverse()
        xml_lines.reverse()
        return clip_text(" ".join(xml_lines), 220), attrs

    def extract(self) -> Dict[str, Any]:
        imports = dedupe_keep_order(self.USING_RE.findall(self.content))
        ns_match = self.NAMESPACE_RE.search(self.content)
        namespace = ns_match.group(1) if ns_match else ""

        classes: List[Dict[str, Any]] = []
        exports: List[str] = []
        all_attrs: List[str] = []
        type_spans: List[tuple[int, str, Dict[str, Any]]] = []

        for match in self.TYPE_RE.finditer(self.content):
            name = match.group("name")
            kind = match.group("kind")
            line_no = self.content[: match.start()].count("\n") + 1
            docstring, attrs = self._preceding_xml_summary_and_attrs(line_no - 1)
            bases_raw = (match.group("bases") or "").strip()
            bases = clip_text(bases_raw, 120) if bases_raw else None
            all_attrs.extend(attrs)

            cls_obj = {
                "name": name,
                "kind": kind if kind != "class" else None,
                "line": line_no,
                "base": bases,
                "attributes": attrs[:5] or None,
                "docstring": docstring or None,
                "methods": [],
            }
            type_spans.append((line_no, name, cls_obj))
            exports.append(name)

        functions: List[Dict[str, Any]] = []
        seen_method_lines = set()
        for match in self.METHOD_RE.finditer(self.content):
            name = match.group("name")
            ret = " ".join(match.group("ret").split())
            if name in self.SKIP_KEYWORDS or ret in self.SKIP_KEYWORDS:
                continue
            # Filter out property-like false matches
            if "=" in ret or ";" in ret:
                continue
            line_no = self.content[: match.start()].count("\n") + 1
            if line_no in seen_method_lines:
                continue
            seen_method_lines.add(line_no)

            mods = match.group("mods") or ""
            is_public = "public" in mods or "protected" in mods
            docstring, attrs = self._preceding_xml_summary_and_attrs(line_no - 1)
            all_attrs.extend(attrs)

            raw_args = match.group("args").strip()
            args: List[str] = []
            if raw_args:
                for part in raw_args.split(","):
                    cleaned = part.strip().split("=")[0].strip()
                    if cleaned:
                        args.append(cleaned.split()[-1])

            func_obj = compact_symbol(
                {
                    "name": name,
                    "line": line_no,
                    "return_type": clip_text(ret, 40),
                    "args": args[:6],
                    "is_async": "async" in mods,
                    "attributes": attrs[:4] or None,
                    "docstring": docstring or None,
                },
                self.include_lines,
            )
            functions.append(func_obj)
            if is_public:
                exports.append(name)

            # Attach method name to nearest preceding enclosing class
            for cls_line, _, cls_obj in reversed(type_spans):
                if cls_line < line_no:
                    if len(cls_obj["methods"]) < 40:
                        cls_obj["methods"].append(name)
                    break

        for _, _, cls_obj in type_spans:
            classes.append(compact_symbol(cls_obj, self.include_lines))

        # Collect semantic clues: routes, tables, DB sets, referenced local types
        route_strings = dedupe_keep_order(self.ROUTE_STRING_RE.findall(self.content), limit=12)
        dbsets = dedupe_keep_order(self.DBSET_RE.findall(self.content), limit=20)
        type_names_defined = {c["name"] for c in classes}
        local_refs = [
            ref
            for ref in dedupe_keep_order(self.LOCAL_TYPE_REF_RE.findall(self.content), limit=25)
            if ref not in type_names_defined
        ]
        project_usings = [u for u in imports if not u.startswith(("System", "Microsoft"))]

        notes: List[str] = []
        if project_usings:
            notes.append("Namespaces internos: " + ", ".join(project_usings[:6]))
        if local_refs:
            notes.append("Dependencias/Tipos referenciados: " + ", ".join(local_refs[:8]))
        if dbsets:
            notes.append("Entidades DbSet: " + ", ".join(dbsets[:10]))
        if route_strings:
            notes.append("Rutas/Tablas: " + ", ".join(route_strings[:8]))

        attr_tokens = [a.split("(")[0].strip() for a in all_attrs if a]
        keywords = dedupe_keep_order(
            route_strings + dbsets + local_refs + attr_tokens + project_usings,
            limit=25,
        )

        return {
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "exports": dedupe_keep_order(exports),
            "namespace": namespace,
            "header_doc": extract_header_comment(self.content, "//"),
            "references": dedupe_keep_order(local_refs + dbsets),
            "context_notes": notes,
            "keywords": keywords,
        }
