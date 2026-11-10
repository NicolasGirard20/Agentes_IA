#!/usr/bin/env python3
"""Genera el documento base de requisitos del producto sin sobrescribirlo."""

import os
import sys
from pathlib import Path


def generate_requirements(project_name):
    return f"""# {project_name} - Requisitos del producto

> Documento de referencia para product-owner, planificador, arquitecto, constructor y tester. Completa las secciones pendientes antes de implementar funcionalidades que cambien el alcance del producto.

## Objetivo del producto

- Pendiente de definir.

## Actores y permisos

- Pendiente de definir actores, roles y permisos.

## Requerimientos funcionales

- RF-01: Pendiente de definir.
  - Criterios de aceptacion: Pendiente de definir.

## Atributos de calidad

- Seguridad: Pendiente de definir.
- Rendimiento: Pendiente de definir.
- Disponibilidad: Pendiente de definir.
- Accesibilidad: Pendiente de definir.
- Observabilidad y mantenibilidad: Pendiente de definir.

## Restricciones

- Tecnicas: Pendiente de definir.
- Operativas: Pendiente de definir.
- Legales o regulatorias: Pendiente de definir.
- Integraciones y dependencias: Pendiente de definir.

## Reglas de negocio

- RN-01: Pendiente de definir.

## Fuera de alcance

- Pendiente de definir.

## Preguntas abiertas

- P-01: ¿Que problema de negocio debe resolver el producto?
- P-02: ¿Quienes son los usuarios y que permisos tiene cada rol?
- P-03: ¿Como se medira que una funcionalidad esta terminada y es exitosa?
"""


def main():
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    project_name = project_root.name
    output = project_root / "PRODUCT_REQUIREMENTS.md"
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        print(f"PRODUCT_REQUIREMENTS.md ya existe; se conserva: {output}")
        return

    output.write_text(generate_requirements(project_name), encoding="utf-8")
    print(f"PRODUCT_REQUIREMENTS.md generado: {output}")


if __name__ == "__main__":
    main()
