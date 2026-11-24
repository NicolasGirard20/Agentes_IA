#!/usr/bin/env python3
"""Genera DESIGN.md con restricciones arquitectonicas basadas en el stack detectado."""

import json
import os
import sys
from pathlib import Path


ALWAYS_ON_FRONTMATTER = "---\ntrigger: always_on\n---\n\n"

DISCOVERY_RULES_SECTION = """## Descubrimiento de archivos (`rag-json` y `project-mapper-simple`)

Si estan presentes las skills `rag-json` y/o `project-mapper-simple` (en `.agents/skills/`, `local/.agents/skills/`, o `~/.gemini/config/skills/` / `$env:USERPROFILE\\.gemini\\config\\skills/`), **usalas obligatoriamente** antes de leer codigo fuente y **evita buscar archivos manualmente** (`read_file` a ciegas, `rg`, `grep`, `Select-String`, `Get-ChildItem`, `find`):

1. **Prioridad por defecto (`rag-json`):**
   - Ubica `rag-json` y ejecuta consultas conceptuales cortas para localizar solo los archivos relevantes sin cargar `project_map.json` en contexto:
     - **Windows (PowerShell):** `<skill_rag>\\.venv\\Scripts\\python.exe <skill_rag>\\scripts\\search_readme_openrouter.py --map <project_map_path.json> --rag "<consulta corta>"` (o `bash <skill_rag>/scripts/rag.sh ...`).
     - **Linux / Bash:** `bash <skill_rag>/scripts/rag.sh --map <project_map_path.json> "<consulta corta>"`.
     - *(Omiti `--map` solo si ya existe `.agents/skills/project-mapper-simple/resources/project_map.json`.)*
   - Si `project_map.json` no existe todavia (o `rag-json` devuelve exit `11` / `MAP_NOT_FOUND`), genera el mapa **completo** (sin `--light`, para conservar `context`, `keywords`, `docstrings` y metodos) y volve a consultar con `rag-json` (sin leer `project_map.json` en contexto):
     - `python <skill_mapper>/scripts/generate_map.py --project . --output <skill_mapper>/resources/project_map.json` (o `python3` / `py`).
   - Lee con `read_file` unicamente los archivos relevantes devueltos por `rag-json`.

2. **Fallback controlado (`project-mapper-simple`):**
   - Usa `project-mapper-simple` directamente **solo** si `rag-json` no esta disponible o falla (skill faltante, falta `OPENROUTER_API_KEY` [exit `2`], Qdrant caido [exit `10`], falta `.venv`/dependencias o error de ejecucion).
   - Genera el mapa (podes usar `--light` y `--exclude "<patron>"` si hace falta reducir tamano) y verifica su tamano:
     - **Si `<= 150` archivos y `<= 40 KB`:** inspecciona el mapa para ubicar los archivos relevantes y lee solo esos archivos puntuales con `read_file`.
     - **Si supera `> 150` archivos o `> 40 KB`** (incluso tras `--light` / `--exclude`), o si `run_command` esta bloqueado, o ninguna de las dos skills puede ejecutarse: **detenete inmediatamente y reporta `BLOCKED`** indicando la causa exacta. No recorras directorios ni busques archivos manualmente uno por uno.
"""


def ensure_design_metadata(content):
    """Asegura el frontmatter trigger: always_on y la regla de rag-json/project-mapper-simple."""
    stripped = content.lstrip("\ufeff")
    if stripped.startswith("---\n") or stripped.startswith("---\r\n"):
        sep = "\r\n" if stripped.startswith("---\r\n") else "\n"
        end_idx = stripped.find(f"{sep}---", 3)
        if end_idx != -1:
            fm = stripped[4:end_idx]
            if "trigger:" not in fm:
                stripped = f"---{sep}trigger: always_on{sep}{fm}{stripped[end_idx:]}"
        else:
            stripped = ALWAYS_ON_FRONTMATTER + stripped
    else:
        stripped = ALWAYS_ON_FRONTMATTER + stripped

    if "rag-json" not in stripped or "project-mapper-simple" not in stripped:
        stripped = stripped.rstrip() + "\n\n" + DISCOVERY_RULES_SECTION
    return stripped


def _format_context7_section(c7_data):
    """Formatea la seccion de convenciones obtenidas desde MCP Context7."""
    if not isinstance(c7_data, dict) or not c7_data:
        return ""

    libs = c7_data.get("libraries") or ([c7_data["library_id"]] if c7_data.get("library_id") else [])
    conventions = c7_data.get("conventions") or []
    summary = c7_data.get("summary") or ""
    arch = c7_data.get("architecture") or {}
    nom = c7_data.get("nomenclature") or {}

    lines = ["\n## Convenciones oficiales del stack (MCP Context7)\n"]
    if libs:
        lines.append(f"- Librerias consultadas en Context7: `{', '.join(str(x) for x in libs)}`")
    if summary:
        lines.append(f"- Resumen: {summary}")
    for k, v in arch.items():
        lines.append(f"- Arquitectura (`{k}`): `{v}`")
    for k, v in nom.items():
        lines.append(f"- Nomenclatura (`{k}`): `{v}`")
    for item in conventions:
        lines.append(f"- {item}")

    return "\n".join(lines) + "\n"


def generate_design(stack, project_root):
    project_name = stack.get("project_name", os.path.basename(project_root))
    framework = stack.get("framework", "unknown")
    language = stack.get("language", "unknown")
    styling = stack.get("styling") or "no detectado"
    ui_library = stack.get("ui_library") or "no detectada"
    orm = stack.get("orm") or "ninguno detectado"
    auth = stack.get("auth") or "no detectada"
    c7_data = stack.get("context7")
    if not c7_data:
        c7_cache = os.path.join(project_root, ".agents", "rules", ".context7_cache.json")
        if os.path.exists(c7_cache):
            try:
                with open(c7_cache, "r", encoding="utf-8") as f:
                    c7_data = json.load(f)
            except Exception:
                c7_data = None
    c7_section = _format_context7_section(c7_data)

    return f"""{ALWAYS_ON_FRONTMATTER}# {project_name} - Diseno y arquitectura

> Regla de referencia para decisiones arquitectonicas y visuales. Este archivo fue generado por agent-init a partir del stack detectado; debe ajustarse cuando la evidencia del proyecto cambie.

## Stack detectado

- Framework: {framework}
- Lenguaje: {language}
- Estilos: {styling}
- Libreria UI: {ui_library}
- ORM: {orm}
- Autenticacion: {auth}
{c7_section}
{DISCOVERY_RULES_SECTION}
## Arquitectura

- Respeta la estructura de carpetas existente y confirma cualquier cambio estructural en el codigo y los tests.
- Mantiene separadas las responsabilidades de presentacion, dominio, infraestructura y configuracion cuando el proyecto las tenga.
- Reutiliza patrones, componentes, estilos y dependencias existentes antes de crear abstracciones nuevas.
- No inventes endpoints, modelos, tokens visuales ni flujos que no esten respaldados por el proyecto o por requisitos explicitos.

## Interfaz y consistencia

- Usa la libreria de estilos e iconos detectada; no introduzcas otra sin justificarlo.
- Conserva los tokens, componentes y convenciones visuales existentes.
- Verifica estados de carga, vacio, error y responsive cuando modifiques una interfaz.

## Seguridad y calidad

- No incluyas secretos en el codigo, logs ni respuestas.
- Valida entradas antes de persistirlas.
- Ejecuta las verificaciones y el lint disponibles antes de considerar terminado un cambio.
- Actualiza esta guia si cambia el stack, la arquitectura o las convenciones visuales.

## Evidencia pendiente de validar

- Ubicar archivos relevantes con `rag-json` (prioritario) o `project-mapper-simple` (fallback `<= 150` archivos / `<= 40 KB`) antes de tomar decisiones concretas, evitando busquedas manuales.
- Reemplazar las reglas genericas por convenciones observadas en codigo, configuracion y tests.
"""


def main():
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    stack_input = sys.stdin.read() if not sys.stdin.isatty() else "{}"
    stack = json.loads(stack_input) if stack_input.strip() else {}
    output = project_root / ".agents" / "rules" / "DESIGN.md"
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        print(f"DESIGN.md ya existe; se conserva: {output}")
        return

    legacy_agents = project_root / "AGENTS.md"
    if legacy_agents.exists():
        migrated = ensure_design_metadata(legacy_agents.read_text(encoding="utf-8"))
        output.write_text(migrated, encoding="utf-8")
        print(f"AGENTS.md migrado a DESIGN.md: {output}")
        return

    output.write_text(generate_design(stack, str(project_root)), encoding="utf-8")
    print(f"DESIGN.md generado: {output}")


if __name__ == "__main__":
    main()
