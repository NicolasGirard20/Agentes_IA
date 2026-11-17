"""Extractors for SQL, PowerShell, Markdown, and configuration files."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from . import clip_text, compact_symbol, dedupe_keep_order, extract_header_comment


class SqlSymbolExtractor:
    """Extract tables, stored procedures, views, functions, and comments from SQL scripts."""

    CREATE_OBJ_RE = re.compile(
        r"\bCREATE\s+(?:OR\s+ALTER\s+)?(?P<kind>TABLE|PROCEDURE|PROC|VIEW|FUNCTION|TRIGGER)\s+"
        r"(?:\[?(?P<schema>\w+)\]?\.)?\[?(?P<name>[A-Za-z_][\w]*)\]?",
        re.IGNORECASE,
    )
    ALTER_TABLE_RE = re.compile(
        r"\bALTER\s+TABLE\s+(?:\[?(?P<schema>\w+)\]?\.)?\[?(?P<name>[A-Za-z_][\w]*)\]?",
        re.IGNORECASE,
    )
    TABLE_REF_RE = re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(?:\[?(?:\w+)\]?\.)?\[?([A-Za-z_][\w]*)\]?",
        re.IGNORECASE,
    )

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    def extract(self) -> Dict[str, Any]:
        header_doc = extract_header_comment(self.content, "--")
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []
        altered_tables: List[str] = []

        for match in self.CREATE_OBJ_RE.finditer(self.content):
            kind = match.group("kind").upper()
            name = match.group("name")
            line_no = self.content[: match.start()].count("\n") + 1
            if kind == "TABLE":
                classes.append(compact_symbol({"name": name, "kind": "table", "line": line_no}, self.include_lines))
            else:
                functions.append(compact_symbol({"name": name, "kind": kind.lower(), "line": line_no}, self.include_lines))

        for match in self.ALTER_TABLE_RE.finditer(self.content):
            altered_tables.append(match.group("name"))
        altered_tables = dedupe_keep_order(altered_tables, limit=15)

        table_refs = dedupe_keep_order(
            [t for t in self.TABLE_REF_RE.findall(self.content) if t.lower() not in {"select", "sys", "inserted", "deleted"}],
            limit=20,
        )

        notes: List[str] = []
        if classes:
            notes.append("Tablas creadas: " + ", ".join(c["name"] for c in classes[:8]))
        if altered_tables:
            notes.append("Tablas alteradas: " + ", ".join(altered_tables[:8]))
        if functions:
            notes.append("Rutinas/Vistas SQL: " + ", ".join(f["name"] for f in functions[:8]))
        if table_refs:
            notes.append("Tablas referenciadas: " + ", ".join(table_refs[:10]))

        exports = dedupe_keep_order([c["name"] for c in classes] + [f["name"] for f in functions])
        return {
            "imports": table_refs,
            "classes": classes,
            "functions": functions,
            "exports": exports,
            "header_doc": header_doc,
            "references": table_refs,
            "context_notes": notes,
            "keywords": dedupe_keep_order(exports + altered_tables + table_refs, limit=20),
        }


class PowerShellSymbolExtractor:
    """Extract functions, parameters, comments, and invoked scripts from PowerShell files."""

    FUNC_RE = re.compile(r"^\s*function\s+([A-Za-z_][\w-]*)", re.MULTILINE | re.IGNORECASE)
    DOT_SOURCE_RE = re.compile(r"""^\s*\.\s+["']?([^"'\r\n]+\.ps1)["']?""", re.MULTILINE | re.IGNORECASE)

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    def extract(self) -> Dict[str, Any]:
        header_doc = extract_header_comment(self.content, "#")
        functions: List[Dict[str, Any]] = []
        for match in self.FUNC_RE.finditer(self.content):
            line_no = self.content[: match.start()].count("\n") + 1
            functions.append(compact_symbol({"name": match.group(1), "line": line_no}, self.include_lines))

        imports = dedupe_keep_order(self.DOT_SOURCE_RE.findall(self.content), limit=10)
        exports = dedupe_keep_order([f["name"] for f in functions])
        return {
            "imports": imports,
            "classes": [],
            "functions": functions,
            "exports": exports,
            "header_doc": header_doc,
            "references": imports,
            "context_notes": [],
            "keywords": exports[:15],
        }


class MarkdownSymbolExtractor:
    """Extract title, section headings, and first summary paragraph from Markdown docs."""

    HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    def extract(self) -> Dict[str, Any]:
        headings = [(len(m.group(1)), clip_text(m.group(2), 100)) for m in self.HEADING_RE.finditer(self.content)]
        title = ""
        subheadings: List[str] = []
        for level, text in headings:
            if level == 1 and not title:
                title = text
            else:
                subheadings.append(text)
        if not title and subheadings:
            title = subheadings.pop(0)

        # Extract first meaningful non-heading paragraph
        first_para = ""
        for line in self.content.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("---") or s.startswith(">"):
                continue
            first_para = clip_text(s, 220)
            break

        notes: List[str] = []
        if subheadings:
            notes.append("Secciones: " + ", ".join(dedupe_keep_order(subheadings, limit=10)))

        return {
            "imports": [],
            "classes": [],
            "functions": [],
            "exports": [],
            "title": title,
            "header_doc": first_para,
            "references": [],
            "context_notes": notes,
            "keywords": dedupe_keep_order(([title] if title else []) + subheadings, limit=20),
        }


class ConfigSymbolExtractor:
    """Extract non-sensitive structural keys/sections from XML (.config) and JSON files."""

    def __init__(self, content: str, path: Path, language: str):
        self.content = content
        self.path = path
        self.language = language

    def extract(self) -> Dict[str, Any]:
        keys: List[str] = []
        notes: List[str] = []
        title = self.path.name

        if self.language == "json":
            try:
                parsed = json.loads(self.content)
                if isinstance(parsed, dict):
                    keys = [str(k) for k in list(parsed.keys())[:20]]
                    notes.append("Claves raíz JSON: " + ", ".join(keys[:10]))
            except (json.JSONDecodeError, TypeError):
                pass
        elif self.language == "xml":
            try:
                root = ET.fromstring(self.content)
                sections = dedupe_keep_order([child.tag.split("}")[-1] for child in list(root)], limit=15)
                app_keys = dedupe_keep_order(
                    [
                        elem.attrib["key"]
                        for elem in root.findall(".//appSettings/add")
                        if "key" in elem.attrib
                    ],
                    limit=20,
                )
                conn_names = dedupe_keep_order(
                    [
                        elem.attrib["name"]
                        for elem in root.findall(".//connectionStrings/add")
                        if "name" in elem.attrib
                    ],
                    limit=10,
                )
                keys = dedupe_keep_order(sections + app_keys + conn_names, limit=20)
                if sections:
                    notes.append("Secciones XML: " + ", ".join(sections[:8]))
                if app_keys:
                    notes.append("AppSettings keys: " + ", ".join(app_keys[:10]))
                if conn_names:
                    notes.append("ConnectionStrings: " + ", ".join(conn_names[:6]))
            except ET.ParseError:
                pass

        return {
            "imports": [],
            "classes": [],
            "functions": [],
            "exports": [],
            "title": title,
            "header_doc": "",
            "references": [],
            "context_notes": notes,
            "keywords": keys,
        }
