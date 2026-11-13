#!/usr/bin/env bash
# Wrapper de rag-json: valida mapa, API key y Qdrant (rápido), luego prepara venv/dependencias y ejecuta la búsqueda.
# Uso: rag.sh [opciones del script] "consulta"
# Exit codes: 2 = falta OPENROUTER_API_KEY, 10 = Qdrant no responde (preguntar al usuario), 11 = project_map.json no encontrado, 1 = fallo de entorno.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$SKILL_DIR/.venv"
PY="$VENV/bin/python"

find_project_root() {
  local dir="$SKILL_DIR"
  while [ "$dir" != "/" ]; do
    if [ "$(basename "$dir")" = ".agents" ]; then
      local parent
      parent="$(dirname "$dir")"
      if [ "$parent" != "$HOME" ]; then
        echo "$parent"
        return 0
      fi
    fi
    dir="$(dirname "$dir")"
  done

  # Instalación global: buscar raíz del proyecto desde el directorio actual (.agents o .git)
  dir="$(pwd)"
  while [ "$dir" != "/" ]; do
    if { [ -d "$dir/.agents" ] && [ "$dir" != "$HOME" ]; } || [ -e "$dir/.git" ]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done

  pwd
}

PROJECT_ROOT="$(find_project_root)"

has_env_key() {
  local env_file="$1"
  [ -f "$env_file" ] && grep -Eq '^[[:space:]]*(export[[:space:]]+)?OPENROUTER_API_KEY[[:space:]]*=[[:space:]]*["'\'']?[^"'\''#[:space:]]+' "$env_file"
}

# 1. project_map.json y flags (si no viene --map explícito)
ARGS=("$@")
HAS_MAP=0; HAS_FORMAT=0; HAS_API_KEY=0
for a in "${ARGS[@]}"; do
  case "$a" in
    --map|--map=*) HAS_MAP=1 ;;
    --json|--rag) HAS_FORMAT=1 ;;
    --api-key|--api-key=*) HAS_API_KEY=1 ;;
  esac
done

if [ "$HAS_MAP" -eq 0 ]; then
  MAP=""
  if [ -n "${RAG_MAP:-}" ]; then
    MAP="$RAG_MAP"
  else
    for candidate in \
      "$PROJECT_ROOT/.agents/skills/project-mapper/resources/project_map.json" \
      "$PROJECT_ROOT/.agents/skills/project-mapper-simple/resources/project_map.json" \
      "$PROJECT_ROOT/.agents/project_map.json" \
      "$PROJECT_ROOT/project_map.json"; do
      if [ -f "$candidate" ]; then
        MAP="$candidate"
        break
      fi
    done
  fi
  if [ -z "$MAP" ] || [ ! -f "$MAP" ]; then
    echo "MAP_NOT_FOUND: no se encontró project_map.json en $PROJECT_ROOT (generarlo con project-mapper o usar --map <ruta>)." >&2
    exit 11
  fi
  ARGS=(--map "$MAP" "${ARGS[@]}")
fi

# 2. OPENROUTER_API_KEY (fail-fast antes de crear/validar venv o contactar Qdrant)
if [ "$HAS_API_KEY" -eq 0 ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
  FOUND_ENV=0
  for f in "$PROJECT_ROOT/.env" "$SCRIPT_DIR/.env" "$HOME/.gemini/.env"; do
    if has_env_key "$f"; then
      FOUND_ENV=1
      break
    fi
  done
  if [ "$FOUND_ENV" -eq 0 ]; then
    echo "ERROR: Falta OPENROUTER_API_KEY. Definila en $PROJECT_ROOT/.env o ~/.gemini/.env (o exportala / --api-key)." >&2
    exit 2
  fi
fi

# 3. Qdrant activo
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
