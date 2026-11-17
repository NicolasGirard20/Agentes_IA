"""Modular, dependency-free source extractors for project-mapper-simple."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def compact_symbol(symbol: Dict[str, Any], include_lines: bool) -> Dict[str, Any]:
    """Drop empty/default fields to keep each symbol compact."""
    result = {key: value for key, value in symbol.items() if value not in (None, False, [], "")}
    if not include_lines:
        result.pop("line", None)
    return result


def clip_text(text: str, limit: int = 220) -> str:
    """Normalize whitespace and clip text to a maximum length."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def dedupe_keep_order(items: List[str], limit: Optional[int] = None) -> List[str]:
    """Deduplicate non-empty strings preserving insertion order."""
    seen = set()
    out: List[str] = []
    for item in items:
        val = str(item).strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
            if limit is not None and len(out) >= limit:
                break
    return out


def extract_header_comment(content: str, line_prefix: str = "//") -> str:
    """Extract leading single-line or block comments from the top of a file."""
    lines = content.splitlines()[:35]
    collected: List[str] = []
    in_block = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("/*"):
            in_block = True
            inner = stripped.lstrip("/*").rstrip("*/").strip(" *")
            if inner and not inner.startswith("="):
                collected.append(inner)
            if "*/" in stripped[2:]:
                in_block = False
            continue
        if in_block:
            inner = stripped.rstrip("*/").strip(" *=-")
            if inner:
                collected.append(inner)
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith(line_prefix):
            inner = stripped[len(line_prefix):].lstrip("/!# ").strip("=- ")
            if inner and not inner.startswith("<"):
                collected.append(inner)
            continue
        break
    return clip_text(" ".join(collected), 260)


def infer_role(rel_path: str, language: str, extracted: Dict[str, Any]) -> str:
    """Infer an architectural role label from path, language, and extracted symbols."""
    norm = rel_path.replace("\\", "/")
    lower = norm.lower()
    parts = [p.lower() for p in Path(norm).parts]
    stem = Path(norm).stem.lower()

    if any(p in ("tests", "test", "spec", "e2e") or "test" in stem or "spec" in stem for p in parts[:-1]):
        return "Test / Validación"
    if "test" in stem or "spec" in stem or stem.startswith("check_"):
        return "Test / Validación"

    if language == "csharp":
        classes = extracted.get("classes", [])
        bases = " ".join(str(c.get("base", "")) for c in classes).lower()
        if "controllers" in parts or stem.endswith("controller") or "controller" in bases:
            return "Controlador MVC"
        if "dao" in parts or stem.endswith("dao"):
            return "DAO / Acceso a datos"
        if "services" in parts or stem.endswith("service"):
            return "Servicio de negocio"
        if "viewmodels" in parts or stem.endswith("viewmodel") or stem.endswith("vm"):
            return "ViewModel"
        if "filters" in parts or "filter" in bases or "attribute" in bases:
            return "Filtro / Atributo MVC"
        if "dbcontext" in bases:
            return "Contexto de Base de Datos (EF)"
        if "models" in parts:
            return "Modelo / Entidad"
        if "utiles" in parts or "utils" in parts or "helpers" in parts:
            return "Utilidad / Helper"
        if "app_start" in parts:
            return "Configuración de arranque"
        return "Módulo C#"

    if language in ("razor", "html"):
        if "_layout" in stem:
            return "Layout compartido Razor"
        if stem.startswith("_"):
            return "Vista parcial Razor"
        return "Vista Razor"

    if language in ("javascript", "typescript", "jsx", "tsx"):
        if "scripts" in parts or "js" in parts:
            return "Script JS cliente"
        return f"Módulo {language.upper()}"

    if language == "sql":
        return "Script / Migración SQL"
    if language == "powershell":
        return "Script PowerShell"
    if language == "markdown":
        return "Documentación Markdown"
    if language in ("xml", "json"):
        if "config" in stem or lower.endswith(".config"):
            return "Configuración"
        return "Datos / Configuración"
    if language == "css":
        return "Hoja de estilos CSS"
    if language == "python":
        return "Módulo Python"
    return f"Archivo {Path(norm).suffix or 'sin extensión'}"


def build_summary_and_context(
    rel_path: str,
    language: str,
    extracted: Dict[str, Any],
    role: str,
) -> Tuple[str, str, List[str]]:
    """Build a concise natural-language summary, dense RAG context, and keywords."""
    classes = extracted.get("classes", [])
    functions = extracted.get("functions", [])
    notes = extracted.get("context_notes", [])
    raw_keywords = extracted.get("keywords", [])

    class_names = dedupe_keep_order([c["name"] for c in classes if c.get("name")])
    public_funcs = dedupe_keep_order(
        [f["name"] for f in functions if f.get("name") and not f["name"].startswith("_")]
    )

    summary_parts: List[str] = [role]
    if extracted.get("title"):
        summary_parts.append(clip_text(extracted["title"], 90))
    if class_names:
        summary_parts.append("Clases: " + ", ".join(class_names[:4]))
    if public_funcs:
        summary_parts.append("Métodos/Funciones: " + ", ".join(public_funcs[:6]))
    elif notes and not extracted.get("title"):
        summary_parts.append(clip_text(notes[0], 110))

    summary = clip_text(" | ".join(summary_parts), 220)

    context_parts: List[str] = [f"Rol: {role}."]
    if extracted.get("title"):
        context_parts.append(f"Título/Propósito: {clip_text(extracted['title'], 140)}.")
    if extracted.get("namespace"):
        context_parts.append(f"Namespace: {extracted['namespace']}.")
    if extracted.get("header_doc"):
        context_parts.append(f"Descripción: {clip_text(extracted['header_doc'], 220)}.")

    class_docs = [
        f"{c['name']}: {clip_text(c['docstring'], 120)}"
        for c in classes
        if c.get("name") and c.get("docstring")
    ]
    if class_docs:
        context_parts.append("Tipos: " + "; ".join(class_docs[:4]) + ".")

    func_docs = [
        f"{f['name']}: {clip_text(f['docstring'], 100)}"
        for f in functions
        if f.get("name") and f.get("docstring")
    ]
    if func_docs:
        context_parts.append("Operaciones: " + "; ".join(func_docs[:5]) + ".")

    for note in notes[:6]:
        if note:
            context_parts.append(clip_text(note, 180))

    context = clip_text(" ".join(context_parts), 700)

    kw_candidates: List[str] = []
    kw_candidates.extend(raw_keywords)
    kw_candidates.extend(class_names[:8])
    kw_candidates.extend(public_funcs[:12])
    keywords = dedupe_keep_order(kw_candidates, limit=25)
    return summary, context, keywords


def extract_file_info(content: str, path: Path, language: str, include_lines: bool) -> Dict[str, Any]:
    """Dispatch extraction to the appropriate language extractor."""
    from .csharp import CSharpSymbolExtractor
    from .data_docs import (
        ConfigSymbolExtractor,
        MarkdownSymbolExtractor,
        PowerShellSymbolExtractor,
        SqlSymbolExtractor,
    )
    from .python_js import JSSymbolExtractor, PythonSymbolExtractor
    from .razor_web import RazorSymbolExtractor

    if language == "python":
        return PythonSymbolExtractor(content, include_lines).extract()
    if language in ("javascript", "typescript", "jsx", "tsx"):
        return JSSymbolExtractor(content, include_lines).extract()
    if language == "csharp":
        return CSharpSymbolExtractor(content, include_lines).extract()
    if language in ("razor", "html"):
        return RazorSymbolExtractor(content, include_lines).extract()
    if language == "sql":
        return SqlSymbolExtractor(content, include_lines).extract()
    if language == "powershell":
        return PowerShellSymbolExtractor(content, include_lines).extract()
    if language == "markdown":
        return MarkdownSymbolExtractor(content, include_lines).extract()
    if language in ("xml", "json"):
        return ConfigSymbolExtractor(content, path, language).extract()

    return {
        "imports": [],
        "classes": [],
        "functions": [],
        "exports": [],
        "references": [],
        "context_notes": [],
        "keywords": [],
    }
