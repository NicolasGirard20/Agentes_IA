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
Ejecuta `detect_stack.py` que lee `package.json` y detecta:
- Framework (Next.js, React, Vue, Angular)
- ORM (Prisma, Drizzle, TypeORM)
- Estilos (Tailwind, Styled Components, Emotion)
- UI Library (shadcn, Radix, MUI, Ant Design)
- Auth (NextAuth, Clerk, JWT custom)
- Testing (Jest, Vitest)

### Paso 2: Elegir template
Según el stack detectado, elige el template más adecuado:
- `nextjs-prisma/` → Next.js + Prisma + Tailwind + shadcn/ui
- `react-vite/` → React + Vite + Tailwind
- `vanilla-ts/` → Genérico TypeScript
- `dotnet-mvc/` → ASP.NET MVC / .NET Framework + Razor

Si el framework detectado **no tiene template dedicado** (Angular, Vue, Svelte, Astro, Solid, Nuxt, Remix), se usa el **fallback generativo**: `generate_framework_rules.py` genera un `coding-rules.json` y un `DESIGN.md` con reglas específicas del framework.

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
- Si el stack no coincide con ningún template, se genera configuración genérica.