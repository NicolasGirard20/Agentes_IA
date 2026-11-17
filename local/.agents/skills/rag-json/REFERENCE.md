# Referencia avanzada de rag-json

Solo consultar si el uso básico (`scripts/rag.sh "<consulta>"`) no alcanza.

## Ejecución manual (sin wrapper)
Linux/macOS: `<skill>/.venv/bin/python`. Windows: `<skill>\.venv\Scripts\python.exe`.
Crear venv: `python3 -m venv <skill>/.venv` e instalar: `<skill>/.venv/bin/pip install -r <skill>/requirements.txt`.
Qdrant debe responder en `http://localhost:6333/healthz` (HTTP) y `6334` (gRPC).

```bash
<skill>/.venv/bin/python <skill>/scripts/search_readme_openrouter.py --map <project_map.json> --rag "<consulta>"
```

## Opciones
`rag.sh` pasa cualquier opción al script. Si no se indica `--map` ni formato, autodetecta el mapa y agrega `--rag`.
Raíz del proyecto: si la skill está en `<raíz>/.agents/skills/rag-json`, usa `<raíz>`; si está en la ubicación global (`~/.gemini/config/skills/rag-json`), la busca subiendo desde el directorio actual (`.agents` o `.git`, o `$PWD`).
Variables: `RAG_MAP` (override del mapa), `QDRANT_URL` (def. `http://localhost:6333`).
`OPENROUTER_API_KEY`: variable exportada > `<raíz>/.env` > `scripts/.env` > `~/.gemini/.env`.

| Opción | Descripción | Defecto |
|---|---|---|
| `query` | Consulta en lenguaje natural | Requerido |
| `--map` | Ruta a `project_map.json` | autodetectado |
| `--rag` | Salida compacta de una línea por archivo | por defecto en `rag.sh` |
| `--json` | JSON compacto (sin campos de debug) | `False` |
| `--top-k` | Cantidad máxima de archivos | `3` |
| `--min-score` | Score mínimo combinado (0.0–1.0) | `0.2` |
| `--rel-cutoff` | Descarta resultados con score < rel × score del primero (`0` desactiva) | `0.6` |
| `--include-meta` | Incluye docs meta (`[arquitectura]`, `[proyecto]`) | `False` |
| `--reindex` | Fuerza reconstruir la colección en Qdrant | `False` |
| `--verbose` | Mensajes informativos en stderr | `False` |
| `--embed-model` | Modelo de embeddings en OpenRouter | `openai/text-embedding-3-small` |
| `--host` / `--port` | Host / puerto HTTP de Qdrant | `localhost` / `6333` |

## Reindexación
Tras cambios estructurales en `project_map.json`:
```bash
<skill>/scripts/rag.sh --reindex "<consulta>"
```
