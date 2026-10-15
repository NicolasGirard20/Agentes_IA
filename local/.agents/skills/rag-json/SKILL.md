---
name: rag-json
description: Localiza archivos relevantes de un proyecto por consulta en lenguaje natural (RAG híbrido sobre project_map.json con Qdrant y OpenRouter). Usar cuando no se sabe qué archivos implementan algo.
---

# RAG JSON

## Cuándo usar
- Se desconoce qué archivos/módulos implementan una funcionalidad.
- La consulta es conceptual y no coincide con nombres exactos.
- Hay que identificar dependencias o responsabilidades antes de planificar.

**No usar** si el archivo ya es conocido, el cambio es puntual o basta un grep de un término exacto.

## Uso

Un solo comando (resuelve venv, dependencias, Qdrant y mapa):

```bash
.agents/skills/rag-json/scripts/rag.sh "<consulta en lenguaje natural>"
```

Convenciones (relativas a la raíz del proyecto, deducida de la ubicación de la skill; funciona desde cualquier directorio):
- Mapa: `.agents/skills/project-mapper/resources/project_map.json`.
- `OPENROUTER_API_KEY`: en el `.env` de la raíz del proyecto (o exportada; `scripts/.env` solo como respaldo).

Salida: una línea por archivo → `` `ruta` — resumen [símbolos] ``. Por defecto devuelve hasta 3 resultados.

## Códigos de salida
| Código | Acción |
|---|---|
| 0 | Leer solo los archivos listados con `view_file`. |
| 10 | Qdrant caído: **preguntar al usuario** si activa el contenedor; no iniciarlo sin confirmar. Con su OK: `docker start qdrant-local \|\| docker run -d --name qdrant-local -p 6333:6333 -p 6334:6334 qdrant/qdrant` y reintentar. Si rechaza, suspender. |
| 11 | Falta `project_map.json`: generarlo con project-mapper o pasar `--map <ruta>`. |
| 2 | Falta `OPENROUTER_API_KEY`: pedir al usuario que la agregue al `.env` de la raíz. |

## Reglas
- No explorar el árbol ni hacer búsquedas recursivas si la skill ya localizó los archivos.
- Al reportar, enlazar los archivos (`[nombre](file:///ruta)`) y explicar en una frase por qué importan.
- Opciones avanzadas (`--top-k`, `--json`, `--reindex`, etc.): ver [REFERENCE.md](REFERENCE.md), solo si hace falta.
