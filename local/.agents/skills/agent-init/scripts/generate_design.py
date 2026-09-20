#!/usr/bin/env python3
"""Genera DESIGN.md con restricciones arquitectonicas basadas en el stack detectado."""

import json
import os
import sys
from pathlib import Path


def generate_design(stack, project_root):
    project_name = stack.get("project_name", os.path.basename(project_root))
    framework = stack.get("framework", "unknown")
    language = stack.get("language", "unknown")
    styling = stack.get("styling") or "no detectado"
    ui_library = stack.get("ui_library") or "no detectada"
    orm = stack.get("orm") or "ninguno detectado"
    auth = stack.get("auth") or "no detectada"

    return f"""# {project_name} - Diseno y arquitectura

> Regla de referencia para decisiones arquitectonicas y visuales. Este archivo fue generado por agent-init a partir del stack detectado; debe ajustarse cuando la evidencia del proyecto cambie.

## Stack detectado

- Framework: {framework}
- Lenguaje: {language}
- Estilos: {styling}
- Libreria UI: {ui_library}
- ORM: {orm}
- Autenticacion: {auth}

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

- Revisar la estructura real del proyecto con project-mapper antes de tomar decisiones concretas.
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
        output.write_text(legacy_agents.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"AGENTS.md migrado a DESIGN.md: {output}")
        return

    output.write_text(generate_design(stack, str(project_root)), encoding="utf-8")
    print(f"DESIGN.md generado: {output}")


if __name__ == "__main__":
    main()
