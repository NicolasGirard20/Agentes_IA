---
name: agy-cli
description: Usar agy directamente via CLI bash (sin MCP). Activar cuando el usuario pida "usa agy directo" o cuando el MCP falle.
---

# agy via CLI directo

Usa la tool `bash` con el siguiente comando desde el directorio raiz del proyecto:

```bash
agy --print "<prompt>" --model <model-id> --mode <plan|accept-edits>
```

- `--mode plan` — solo lectura (explorar, diagnosticar)
- `--mode accept-edits` — crear o editar archivos
- Pasar siempre `workdir` al tool bash con la raiz del proyecto
- No combinar `--effort` con model-ids que ya tienen sufijo de tier (`-low`, `-medium`, `-high`)

## Modelos

Consultar lista actualizada con `agy models`. Tipicos:

- `gemini-3.8-flash-low` — rapido, tareas simples
- `gemini-3.8-flash-medium` — balance general
- `claude-sonnet-5-5-medium` — razonamiento complejo

## Restricciones
    - Cuando se invoque esta skills es porque las peticiones del usuario solo tienen que ser atendidas mediante agy directamente via CLI bash.
