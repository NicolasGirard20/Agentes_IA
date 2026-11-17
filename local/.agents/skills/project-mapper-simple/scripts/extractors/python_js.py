"""Extractors for Python and JavaScript/TypeScript source files."""

import ast
import re
from typing import Any, Dict, List

from . import clip_text, compact_symbol, dedupe_keep_order, extract_header_comment


class _PythonAstVisitor(ast.NodeVisitor):
    """Extract actual Python definitions, base classes, docstrings, and imports."""

    def __init__(self, include_lines: bool):
        self.include_lines = include_lines
        self.imports: List[str] = []
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.exports: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.extend(alias.name for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        self.imports.append(module)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods = [
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
        symbol = {
            "name": node.name,
            "line": node.lineno,
            "base": ", ".join(bases) if bases else None,
            "docstring": clip_text(ast.get_docstring(node) or "", 200) or None,
            "methods": methods,
        }
        self.classes.append(compact_symbol(symbol, self.include_lines))
        self.exports.append(node.name)
        self.generic_visit(node)

    def _function(self, node: ast.AST, is_async: bool) -> None:
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        symbol = {
            "name": node.name,
            "line": node.lineno,
            "docstring": clip_text(ast.get_docstring(node) or "", 200) or None,
            "is_async": is_async,
            "args": [arg.arg for arg in node.args.args],
        }
        self.functions.append(compact_symbol(symbol, self.include_lines))
        if not node.name.startswith("_"):
            self.exports.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node, False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node, True)


class PythonSymbolExtractor:
    """Wrapper around Python AST extraction with module docstring/comment context."""

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    def extract(self) -> Dict[str, Any]:
        try:
            tree = ast.parse(self.content)
        except SyntaxError:
            return {
                "imports": [],
                "classes": [],
                "functions": [],
                "exports": [],
                "header_doc": extract_header_comment(self.content, "#"),
                "references": [],
                "context_notes": [],
                "keywords": [],
            }

        visitor = _PythonAstVisitor(self.include_lines)
        visitor.visit(tree)
        module_doc = clip_text(ast.get_docstring(tree) or "", 240)
        if not module_doc:
            module_doc = extract_header_comment(self.content, "#")

        return {
            "imports": visitor.imports,
            "classes": visitor.classes,
            "functions": visitor.functions,
            "exports": visitor.exports,
            "header_doc": module_doc,
            "references": [],
            "context_notes": [],
            "keywords": dedupe_keep_order([imp.split(".")[-1] for imp in visitor.imports], limit=10),
        }


class JSSymbolExtractor:
    """Conservative JS/TS extractor with JSDoc, endpoints, and DOM/API context."""

    IMPORT_PATTERNS = (
        r"\bimport\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|[\w$]+)\s+from\s+)?['\"]([^'\"]+)['\"]",
        r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    )
    CLASS_PATTERN = re.compile(
        r"^[ \t]*(?:export\s+)?(?:default\s+)?class\s+([\w$]+)(?:\s+extends\s+([\w$.]+))?",
        re.MULTILINE,
    )
    FUNCTION_PATTERN = re.compile(
        r"^[ \t]*(?:export\s+)?(?:default\s+)?(?P<async>async\s+)?function\s+(?P<name>[\w$]+)\s*\((?P<args>[^)\n]{0,120})\)",
        re.MULTILINE,
    )
    ARROW_PATTERN = re.compile(
        r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
        r"(?P<async>async\s+)?(?:\((?P<args>[^()\n]{0,120})\)|(?P<single>[A-Za-z_$][\w$]*))\s*=>",
        re.MULTILINE,
    )
    METHOD_PATTERN = re.compile(
        r"^[ \t]+(?P<prefix>(?:(?:public|private|protected|static|async|get|set)\s+)*)"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)\n]{0,120})\)\s*\{",
        re.MULTILINE,
    )
    EXPORT_PATTERN = re.compile(
        r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([\w$]+)"
    )
    ENDPOINT_PATTERN = re.compile(
        r"""(?:fetch|axios\.(?:get|post|put|delete)|url\s*:|\$\.(?:get|post|ajax))\s*\(?\s*['"`](/[^'"`\s?]+(?:/[^'"`\s?]+)*)['"`]""",
        re.IGNORECASE,
    )
    JSDOC_BEFORE_RE = re.compile(r"/\*\*([\s\S]{1,600}?)\*/\s*$")

    def __init__(self, content: str, include_lines: bool):
        self.content = content
        self.include_lines = include_lines

    def _preceding_jsdoc(self, start: int) -> str:
        prefix = self.content[max(0, start - 650):start]
        match = self.JSDOC_BEFORE_RE.search(prefix)
        if not match:
            return ""
        lines = [
            re.sub(r"^\s*\*\s?", "", line).strip()
            for line in match.group(1).splitlines()
        ]
        clean = " ".join(l for l in lines if l and not l.startswith("@"))
        return clip_text(clean, 180)

    def _symbol(self, name: str, start: int, **values: Any) -> Dict[str, Any]:
        return compact_symbol(
            {"name": name, "line": self.content[:start].count("\n") + 1, **values},
            self.include_lines,
        )

    def extract(self) -> Dict[str, Any]:
        imports: List[str] = []
        for pattern in self.IMPORT_PATTERNS:
            imports.extend(re.findall(pattern, self.content))
        imports = sorted(set(imports))

        classes: List[Dict[str, Any]] = []
        for match in self.CLASS_PATTERN.finditer(self.content):
            classes.append(
                self._symbol(
                    match.group(1),
                    match.start(),
                    base=match.group(2),
                    docstring=self._preceding_jsdoc(match.start()) or None,
                )
            )

        functions: List[Dict[str, Any]] = []
        seen_lines = set()
        for match in self.FUNCTION_PATTERN.finditer(self.content):
            line = self.content[: match.start()].count("\n") + 1
            seen_lines.add(line)
            args = [a.strip().split("=")[0].strip() for a in match.group("args").split(",") if a.strip()]
            functions.append(
                self._symbol(
                    match.group("name"),
                    match.start(),
                    is_async=bool(match.group("async")),
                    args=args[:6],
                    docstring=self._preceding_jsdoc(match.start()) or None,
                )
            )

        for match in self.ARROW_PATTERN.finditer(self.content):
            line = self.content[: match.start()].count("\n") + 1
            if line in seen_lines:
                continue
            seen_lines.add(line)
            raw_args = match.group("args") or match.group("single") or ""
            args = [a.strip().split("=")[0].strip() for a in raw_args.split(",") if a.strip()]
            functions.append(
                self._symbol(
                    match.group("name"),
                    match.start(),
                    is_async=bool(match.group("async")),
                    args=args[:6],
                    docstring=self._preceding_jsdoc(match.start()) or None,
                )
            )

        reserved = {"if", "for", "while", "switch", "catch", "with", "else", "function"}
        for match in self.METHOD_PATTERN.finditer(self.content):
            name = match.group("name")
            line = self.content[: match.start()].count("\n") + 1
            if name in reserved or line in seen_lines:
                continue
            seen_lines.add(line)
            functions.append(
                self._symbol(
                    name,
                    match.start(),
                    is_async="async" in (match.group("prefix") or ""),
                    docstring=self._preceding_jsdoc(match.start()) or None,
                )
            )

        functions.sort(key=lambda symbol: symbol.get("line", 0))
        exports = sorted(set(match.group(1) for match in self.EXPORT_PATTERN.finditer(self.content)))
        endpoints = dedupe_keep_order(self.ENDPOINT_PATTERN.findall(self.content), limit=12)

        notes: List[str] = []
        if endpoints:
            notes.append("Endpoints consumidos: " + ", ".join(endpoints[:6]))

        return {
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "exports": exports,
            "header_doc": extract_header_comment(self.content, "//"),
            "references": endpoints,
            "context_notes": notes,
            "keywords": dedupe_keep_order(endpoints + exports, limit=15),
        }
