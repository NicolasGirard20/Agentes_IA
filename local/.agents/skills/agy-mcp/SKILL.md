---
name: agy-mcp
description: Como delegar tareas al sub-agente agy via el servidor MCP agy-agent-mcp (general_task, explore_task, watch_task, list_models, list_agents) sin timeouts, rechazos de argumentos, reintentos ni gasto innecesario de tokens. Usar cuando el usuario pida "usa agy" o cuando se delegue trabajo a agy.
---

# Uso eficiente del MCP agy (`agy-agent-mcp`)

> Nota: Segun como este registrado el MCP en el cliente, las tools se llaman `agy_<tool>` (ej. `agy_general_task`) o `<tool>` (`general_task`).

## Reglas de oro
1. **En este cliente, usa `background: true`** en `general_task` y `explore_task` si la tarea lee mas de 1-2 archivos o edita. Las llamadas bloqueantes pueden expirar a los ~60-80 s (`-32001 Request timed out`); otros clientes pueden permitir el modo bloqueante.
2. **En `watch_task`: evita `wait: true` en este cliente y usa `tail_lines: 25`.** `wait: true` puede sufrir el mismo timeout; el default `tail_lines: 400` trae demasiado transcript en cada poll. Consulta con `watch_task(stream_file=task_id, tail_lines=25)` y repite solo si `running: true`. `stream_file` acepta el ID de tarea o la ruta del `.stream`.
3. **Un `cancelled` o `timeout` NO significa que fallo.** Antes de reintentar, revisa `files_touched`, `response` y las ultimas lineas del `.stream`. Si el archivo ya se escribio, solo verifica; no reenvies el prompt.
4. **Nunca reenvies el mismo prompt.** Para corregir o continuar, reanuda pasando `conversation_id` y un prompt corto solo con la correccion.
5. **Prompt corto (≤ 12 lineas).** `agy` lee archivos solo: dale rutas absolutas/relativas a `cwd`, no pegues el contenido de los archivos ni repitas reglas que ya estan en ellos.
6. **No paralelices `general_task` sobre el mismo árbol de trabajo.** `files_touched` y `scope_violations` se calculan via `git status`; correr ediciones simultáneas ahí puede mezclar la auditoría (`audit_note`). Para paralelizar, usa worktrees/directorios separados. `explore_task` sí puede ir en paralelo.

## Tools y parametros

| Tool | Modo CLI | Default `effort` | Uso y parametros clave |
|---|---|---|---|
| `explore_task` | `plan` (read-only) | `low` | Leer, buscar, diagnosticar o verificar. `background: true` si son varios archivos. |
| `general_task` | `accept-edits` | `medium` | Crear/editar archivos. **`edit_scope` obligatorio** (array de rutas exactas) y **`cwd`** = raiz del proyecto. |
| `watch_task` | — | — | `stream_file: <task_id>`, `tail_lines: 25`. Para abortar: `cancel: true` (nunca junto con `wait: true`). |
| `list_models` / `list_agents` | — | — | Descubrir modelos o perfiles de agente. **Llamar con `{}` sin argumentos** (cualquier argumento es rechazado). |

### Cuidados con los argumentos (evitar llamadas rechazadas `isError: true`)
- **`effort` vs `model`:** No pases `effort` si el default ya te sirve. **Prohibido** pasar `effort` si `model` ya incluye sufijo de tier (ej. `gemini-3.8-flash-high`), el servidor rechaza la combinacion antes de spawnear.
- **Permisos headless (`denied_actions`):** `accept-edits` aprueba ediciones de archivos, pero deniega automaticamente comandos o tools que pidan confirmacion interactiva y los lista en `denied_actions`. No uses `auto_approve: true` salvo pedido explicito del usuario (y si lo pide, combinalo con `sandbox: true`).
- **Si aparece `denied_actions`:** revisa si corresponde permitir esa acción en `permissions.allow` de `settings.json`; no reintentes sin resolver la causa.
- **`add_dirs`:** Si `agy` debe leer carpetas fuera de `cwd`, pasalas en `add_dirs: ["/ruta/extra"]`.
- **`timeout_ms`:** Dejar el default (`900000` ms de idle timeout).

## Plantilla de prompt
```
Objetivo: <1 frase>.
Archivo(s): <ruta>. Edita SOLO eso.
Leer antes: <rutas de referencia, si hacen falta>.
Cambios: <3-6 bullets concretos>.
Restricciones: <idioma/tono/tamano>. No ejecutes git ni comandos interactivos.
Al terminar: reporta solo n° de lineas y resumen en 3 lineas.
```

## Flujo recomendado
1. Lanzar con `background: true` → guardar `task_id`.
2. Hacer poll con `watch_task(stream_file=task_id, tail_lines=25)` mirando `running`, `phase` y `step_count`.
3. Al terminar (`running: false`), revisar `status` (`success` | `error` | `timeout` | `quota_error`), `response`, `files_touched`, `scope_violations` y `denied_actions`.
4. Verificar barato con `explore_task`:
   > "En `<ruta>`: devuelve `wc -l`, y si aparecen (si/no) estas cadenas: X, Y, Z. No devuelvas el contenido completo."

## Errores comunes
- Prompt enorme que duplica el archivo → gasto de tokens x cada reintento.
- Llamada bloqueante larga o `wait: true` en watch → timeout `-32001`.
- Hacer poll en `watch_task` sin `tail_lines: 25` → trae 400 lineas por llamada.
- Pasar `effort` junto con un `model` que ya tiene sufijo (`-low`/`-medium`/`-high`) → llamada rechazada (`isError: true`).
- Reintentar a ciegas sin mirar `files_touched` ni `denied_actions` → trabajo duplicado.
- Usar `agy` para algo trivial (1 edicion puntual): hacerlo directo con las tools propias, salvo que el usuario exija `agy`.

## Si el usuario dice "solo agy"
No uses `edit`/`write`/`bash` propios para el cambio; delega todo (incluida la verificacion) a `agy` siguiendo las reglas de arriba.
