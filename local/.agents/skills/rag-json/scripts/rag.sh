#!/usr/bin/env bash
# Wrapper de rag-json: valida mapa y Qdrant (rápido), luego prepara venv/dependencias y ejecuta la búsqueda.
# Uso: rag.sh [opciones del script] "consulta"
# Exit codes: 10 = Qdrant no responde (preguntar al usuario), 11 = project_map.json no encontrado, 1 = fallo de entorno.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
# Layout fijo: <raíz>/.agents/skills/rag-json -> la raíz está 3 niveles arriba
PROJECT_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
VENV="$SKILL_DIR/.venv"
PY="$VENV/bin/python"

# 1. project_map.json (si no viene --map explícito)
ARGS=("$@")
HAS_MAP=0; HAS_FORMAT=0
for a in "${ARGS[@]}"; do
  case "$a" in
    --map|--map=*) HAS_MAP=1 ;;
    --json|--rag) HAS_FORMAT=1 ;;
  esac
done

if [ "$HAS_MAP" -eq 0 ]; then
  MAP="${RAG_MAP:-$PROJECT_ROOT/.agents/skills/project-mapper/resources/project_map.json}"
  if [ ! -f "$MAP" ]; then
    echo "MAP_NOT_FOUND: no existe $MAP (generarlo con project-mapper o usar --map)." >&2
    exit 11
  fi
  ARGS=(--map "$MAP" "${ARGS[@]}")
fi

# 2. Qdrant activo
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
if ! curl -s -f -m 3 "$QDRANT_URL/healthz" >/dev/null 2>&1; then
  echo "QDRANT_DOWN: sin respuesta en $QDRANT_URL. Preguntar al usuario si activa el contenedor (docker start qdrant-local || docker run -d --name qdrant-local -p 6333:6333 -p 6334:6334 qdrant/qdrant)." >&2
  exit 10
fi

# 3. Entorno virtual y dependencias (solo si faltan; es el paso lento)
if [ ! -x "$PY" ]; then
  if ! python3 -m venv "$VENV" >&2; then
    echo "ERROR: no se pudo crear el venv. En Debian/Ubuntu instalar: sudo apt install python3-venv" >&2
    exit 1
  fi
fi
if ! "$PY" -c "import qdrant_client, numpy" >/dev/null 2>&1; then
  "$VENV/bin/pip" install -q -r "$SKILL_DIR/requirements.txt" >&2 || { echo "ERROR: fallo pip install" >&2; exit 1; }
fi

# 4. Formato compacto por defecto
if [ "$HAS_FORMAT" -eq 0 ]; then
  ARGS=(--rag "${ARGS[@]}")
fi

exec "$PY" "$SCRIPT_DIR/search_readme_openrouter.py" "${ARGS[@]}"
