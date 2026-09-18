# Agentes IA — Configuración de Skills

Este repositorio contiene la **configuración de agentes y skills** utilizada para potenciar el flujo de trabajo con IA en proyectos de software.


### Skills disponibles

| Skill | ¿Para qué sirve? |
|-------|------------------|
| `agent-init` | Scaffolding automático al iniciar un proyecto nuevo. Detecta el stack tecnológico y genera los archivos base de configuración. Si el framework no tiene template dedicado (Angular, Vue, Svelte, Astro, Solid, Nuxt, Remix, etc.), genera reglas específicas de forma automática. |
| `project-mapper` | Mapea la estructura completa del proyecto, comprime el contexto e inyecta solo lo relevante para cada tarea. |
| `prompt-toolkit` | Biblioteca de **templates de prompts** reutilizables y **validador de seguridad** (longitud, coherencia, detección de inyecciones). |
| `improve-design` | Mejora el formato, la estructura y el diseño visual de documentos manteniendo el contenido original. |
| `mejora-diseno` | Versión en español de `improve-design`. Misma funcionalidad, disponible globalmente. |

### Agentes disponibles

Los agentes son roles especializados que colaboran durante el desarrollo. La configuración de Gemini se encuentra en `general/gemini/.gemini/config/agents/`.

| Agente | Responsabilidad |
|--------|----------------|
| `orquestador` | Coordina el flujo completo y delega cada etapa al agente adecuado. |
| `planificador` | Analiza la tarea, revisa el contexto y prepara un plan detallado sin modificar archivos. |
| `arquitecto` | Valida el plan y define la solución técnica, sus límites, riesgos y decisiones de diseño. |
| `constructor` | Implementa la solución, ejecuta las verificaciones locales y propone un commit. |
| `tester` | Ejecuta las pruebas relevantes, identifica fallos y reporta riesgos o cobertura pendiente. |
| `buscador` | Investiga información técnica en internet usando fuentes verificables. |

El flujo recomendado es:

```text
orquestador -> planificador -> arquitecto -> constructor -> tester
```

`buscador` se incorpora únicamente cuando la tarea requiere documentación externa, comparar alternativas o verificar una decisión técnica actual. El `orquestador` debe solicitar la aprobación del plan antes de pasar a la arquitectura y la implementación.

OpenCode también incluye agentes configurados en `general/opencode/.opencode/opencode.json`: `build` para implementar, `plan` para analizar, `quick-review` para revisiones rápidas, `deep-reasoning` para problemas complejos y `git` para operaciones de versionado.

## Configuración global

- **`.opencode/opencode.json`** — Archivo de configuración global de **OpenCode**. Define el modelo por defecto, temperaturas, subagentes especializados (plan, build, review, git) y permisos.

## Inicialización rápida

Para preparar un proyecto nuevo con esta configuración:

```bash
bash .agents/init.sh
```

`init.sh` verifica si existe `.opencode/config.json`; si no, ejecuta el scaffolding de `agent-init`. Luego regenera el mapa del proyecto con `project-mapper` si el mapa existente tiene más de 2 horas. También advierte si falta el validador de `prompt-toolkit`.
