---
name: agent-init
description: >-
  Scaffolding automático de configuración de agentes para cualquier proyecto.
  Detecta el stack tecnológico, genera .opencode/config.json, .agents/rules/coding-rules.json,
  DESIGN.md unificado con reglas de negocio, arquitectura y diseño. Se activa automáticamente en la primera sesión
  de un proyecto nuevo.
---

# Agent Init — Scaffolding de Configuración de Agentes

## Objetivo
Inicializar la configuración de agentes de IA en cualquier proyecto nuevo de forma automática,
detectando el stack tecnológico y generando los archivos específicos del proyecto.

## Cuándo activar esta skill
- En la PRIMERA sesión de trabajo en un proyecto nuevo.
- Cuando el usuario pide "inicializar configuración de agentes", "scaffolding", "setup del proyecto".
- Cuando `.opencode/config.json` no existe en el proyecto.

## Flujo de trabajo

### Paso 1: Detectar stack
Ejecuta `detect_stack.py` que lee `package.json` (o archivos de proyecto equivalentes como `.csproj`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `composer.json`) y detecta:
- Framework (Next.js, React, Vue, Angular, Svelte, Astro, Solid, Nuxt, Remix, NestJS, Express, Fastify, Hono, Expo, FastAPI, Django, Flask, Laravel, etc.)
- ORM (Prisma, Drizzle, TypeORM, Mongoose, Sequelize, SQLAlchemy, Entity Framework)
- Estilos (Tailwind, Styled Components, Emotion, Sass, Bootstrap)
- UI Library (shadcn, Radix, MUI, Ant Design, Chakra)
- Auth (NextAuth, Clerk, JWT custom, ASP.NET Identity)
- Testing (Jest, Vitest, Pytest)
- `has_dedicated_template` (`true`/`false`), `needs_context7` (`true`/`false`) y `context7_candidates` (lista de librerías y queries listas para consultar en MCP Context7).

### Paso 2: Elegir template o consultar MCP Context7 (antes del fallback genérico)
Sigue estrictamente este orden de prioridad:

1. **Template dedicado** (cuando `has_dedicated_template: true`):
   - `nextjs-prisma/` → Next.js + Prisma + Tailwind + shadcn/ui
   - `react-vite/` → React + Vite + Tailwind
   - `dotnet-mvc/` → ASP.NET MVC / .NET Framework + Razor

2. **Consulta en MCP Context7** (cuando el framework o combinación de stack **no tiene template dedicado**, es decir `needs_context7: true`):
   - **Antes de utilizar el fallback estático o el template genérico (`vanilla-ts/`)**, consulta el servidor MCP `context7` usando los candidatos de `context7_candidates` devueltos por `detect_stack.py`:
     1. Llama a `resolve-library-id` con el `libraryName` y `query` del framework principal (y ORM/UI library si aplica).
     2. Llama a `query-docs` con el Library ID obtenido para recuperar la estructura de carpetas oficial, convenciones de nomenclatura, patrones de arquitectura y buenas prácticas del framework.
     3. Guarda las reglas extraídas en `.agents/rules/.context7_cache.json` con la siguiente estructura:
        ```json
        {
          "libraries": ["/org/project"],
          "summary": "Resumen arquitectónico oficial obtenido de Context7",
          "nomenclature": {
            "components": "...",
            "services": "...",
            "folders": "kebab-case"
          },
          "architecture": {
            "routes_path": "...",
            "components_path": "...",
            "services_path": "..."
          },
          "framework_rules": {
            "regla_clave": true
          },
          "conventions": [
            "Convención oficial 1 extraída de Context7",
            "Convención oficial 2 extraída de Context7"
          ]
        }
        ```
     4. Ejecuta `generate_framework_rules.py` pasando `--context7-file .agents/rules/.context7_cache.json` (o `init_project.sh --context7-file .agents/rules/.context7_cache.json`), lo que inyecta la configuración oficial en `.agents/rules/coding-rules.json` (`"source": "context7"`) y en `.agents/rules/DESIGN.md`.

3. **Fallback estático / genérico (`vanilla-ts/`)**:
   - Solo si el servidor MCP `context7` no está disponible o no arroja resultados para las librerías del proyecto, utiliza las reglas estáticas de `generate_framework_rules.py` o el template genérico `vanilla-ts/`.

### Paso 3: Generar archivos
- `.opencode/config.json` → Configuración técnica del agente
- `.agents/rules/coding-rules.json` → Reglas estructuradas del proyecto
- `.agents/rules/DESIGN.md` → Documento unificado de negocio, arquitectura, diseño y convenciones

### Paso 4: Generar mapa inicial
Ejecuta `project-mapper-simple` (`scripts/generate_map.py`) para generar el primer mapa del proyecto.
Esta skill NO genera `PRODUCT_REQUIREMENTS.md`.

### Paso 5: Agregar carpeta local del agente al gitignore
Agrega .agents/ al gitignore en el proyecto local

## Salida esperada
```
.opencode/config.json
.agents/rules/coding-rules.json
.agents/rules/DESIGN.md
.agents/skills/project-mapper-simple/resources/project_map.json
AGENTS.md   (indicaciones para actualizar .agents; ver "AGENTS.md y hallazgos")
```

## AGENTS.md y hallazgos

Cuando el agente detecte, con evidencia real (sin suponer ni inventar):
- **repetitive**: una tarea o corrección que se repite.
- **error**: un error descubierto sobre la app.
- **design**: una referencia de diseño nueva o modificada.

Debe registrarlo desde el proyecto con:

```bash
python3 .agents/skills/agent-init/scripts/update_agents_md.py \
  --project . --category <repetitive|error|design> --text "<indicación>" \
  [--rule-key <clave.con.puntos> --rule-value '<JSON>']
```

- Crea/actualiza `AGENTS.md` en la raíz como **punto de referencia hacia `.agents/`**: solo indicaciones de cómo actualizar `.agents/` (tabla de qué corregir y dónde + comando). No describe el proyecto ni lista skills/rules. Solo reescribe el bloque `<!-- agent-init:start --> ... <!-- agent-init:end -->`; el resto se conserva.
- El hallazgo se guarda en `.agents/rules/LEARNINGS.md` (no en AGENTS.md), y luego se resincroniza el índice.
- Con `--rule-key/--rule-value` actualiza `.agents/rules/coding-rules.json`.
- Con `category=design` agrega además la nota en `.agents/rules/DESIGN.md` (sección "Cambios de diseño registrados").
- `--sync` regenera solo el bloque de AGENTS.md.
- Los agentes deben leer `AGENTS.md` para saber qué corregir dentro de `.agents`.
- Si hay duda sobre qué registrar o en qué regla, preguntar al usuario antes de escribir.

## Validación
- Verificar que los JSON generados sean válidos.
- Verificar que `.agents/rules/DESIGN.md` exista y tenga las secciones mínimas.
- Verificar que `DESIGN.md` no se haya sobrescrito si ya estaba personalizado.
- Si el stack no coincide con ningún template dedicado, verificar que primero se haya intentado consultar MCP `context7` (`"source": "context7"` en `coding-rules.json`) antes de caer en la configuración genérica.