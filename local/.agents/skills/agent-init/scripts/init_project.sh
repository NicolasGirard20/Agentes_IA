#!/bin/bash
# init_project.sh — Scaffolding automático de configuración de agentes para cualquier proyecto
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/../templates"
CONTEXT7_FILE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --context7-file)
            CONTEXT7_FILE="$2"
            shift 2
            ;;
        --project)
            PROJECT_ROOT="$(cd "$2" && pwd)"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$CONTEXT7_FILE" ] && [ -f "$PROJECT_ROOT/.agents/rules/.context7_cache.json" ]; then
    CONTEXT7_FILE="$PROJECT_ROOT/.agents/rules/.context7_cache.json"
fi

echo "=== Scaffolding de Agentes para: $(basename "$PROJECT_ROOT") ==="

# Detectar binario de Python
PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "python")

# Paso 1: Detectar stack
echo "[1/4] Detectando stack tecnológico..."
STACK_JSON=$("$PYTHON_BIN" "$SCRIPT_DIR/detect_stack.py" "$PROJECT_ROOT")
FRAMEWORK=$(echo "$STACK_JSON" | "$PYTHON_BIN" -c "import sys,json; print(json.load(sys.stdin).get('framework','unknown'))")
echo "  Framework detectado: $FRAMEWORK"

# Paso 2: Elegir template (o consultar Context7 antes del fallback genérico)
TEMPLATE_DIR=""
USE_FRAMEWORK_FALLBACK=""
case "$FRAMEWORK" in
    dotnet-mvc|aspnet-mvc)
        TEMPLATE_DIR="$TEMPLATES_DIR/dotnet-mvc"
        echo "  Template dedicado: dotnet-mvc"
        ;;
    nextjs)
        if echo "$STACK_JSON" | "$PYTHON_BIN" -c "import sys,json; s=json.load(sys.stdin); exit(0 if s.get('orm')=='prisma' else 1)" 2>/dev/null; then
            TEMPLATE_DIR="$TEMPLATES_DIR/nextjs-prisma"
            echo "  Template dedicado: nextjs-prisma"
        elif [ -n "$CONTEXT7_FILE" ] && [ -f "$CONTEXT7_FILE" ]; then
            USE_FRAMEWORK_FALLBACK="1"
            echo "  Next.js sin Prisma: aplicando configuración enriquecida con MCP Context7"
        else
            echo "  Next.js sin template dedicado (se recomienda consultar MCP Context7; usando scaffold_rules.py)"
        fi
        ;;
    react-vite|react)
        TEMPLATE_DIR="$TEMPLATES_DIR/react-vite"
        echo "  Template dedicado: react-vite"
        ;;
    *)
        USE_FRAMEWORK_FALLBACK="1"
        if [ -n "$CONTEXT7_FILE" ] && [ -f "$CONTEXT7_FILE" ]; then
            echo "  Framework sin template dedicado ($FRAMEWORK): usando datos de MCP Context7 ($CONTEXT7_FILE)"
        else
            echo "  WARN: Framework '$FRAMEWORK' no tiene template dedicado y aún no hay datos de MCP Context7."
            echo "        El agente debe consultar MCP Context7 (resolve-library-id + query-docs) antes de usar el genérico."
            if [ "$FRAMEWORK" = "unknown" ]; then
                TEMPLATE_DIR="$TEMPLATES_DIR/vanilla-ts"
                echo "        Aplicando fallback genérico temporal: vanilla-ts"
            fi
        fi
        ;;
esac

# Paso 3: Generar archivos de configuración
echo "[2/4] Generando .opencode/config.json..."
echo "$STACK_JSON" | "$PYTHON_BIN" "$SCRIPT_DIR/generate_config.py" "$PROJECT_ROOT"

echo "[3/4] Generando coding-rules.json y DESIGN.md..."
if [ -n "$USE_FRAMEWORK_FALLBACK" ]; then
    if [ -n "$CONTEXT7_FILE" ] && [ -f "$CONTEXT7_FILE" ]; then
        echo "  Generando reglas de $FRAMEWORK con MCP Context7..."
        echo "$STACK_JSON" | "$PYTHON_BIN" "$SCRIPT_DIR/generate_framework_rules.py" "$PROJECT_ROOT" --context7-file "$CONTEXT7_FILE"
    else
        echo "  Generando reglas de $FRAMEWORK (fallback)..."
        echo "$STACK_JSON" | "$PYTHON_BIN" "$SCRIPT_DIR/generate_framework_rules.py" "$PROJECT_ROOT"
    fi
else
    echo "$STACK_JSON" | "$PYTHON_BIN" "$SCRIPT_DIR/scaffold_rules.py" "$PROJECT_ROOT"
fi

# Si existe template, copiar y reemplazar placeholders
if [ -n "$TEMPLATE_DIR" ] && [ -d "$TEMPLATE_DIR" ]; then
    echo "[3b/4] Aplicando template: $(basename "$TEMPLATE_DIR")..."
    PROJECT_NAME=$(basename "$PROJECT_ROOT")

    for tmpl_file in "$TEMPLATE_DIR"/*.json; do
        if [ -f "$tmpl_file" ]; then
            filename=$(basename "$tmpl_file")
            target=""
            case "$filename" in
                config.json) target="$PROJECT_ROOT/.opencode/config.json" ;;
                coding-rules.json) target="$PROJECT_ROOT/.agents/rules/coding-rules.json" ;;
            esac
            if [ -n "$target" ]; then
                sed "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$tmpl_file" > "$target"
                echo "    $filename aplicado"
            fi
        fi
    done
fi

# Paso 4: Ejecutar project-mapper-simple por primera vez
echo "[4/4] Generando mapa inicial del proyecto..."
if [ -f "$PROJECT_ROOT/.agents/skills/project-mapper-simple/scripts/generate_map.py" ]; then
    "$PYTHON_BIN" "$PROJECT_ROOT/.agents/skills/project-mapper-simple/scripts/generate_map.py" \
        --project "$PROJECT_ROOT" \
        --output "$PROJECT_ROOT/.agents/skills/project-mapper-simple/resources/project_map.json" \
        --force
    echo "  Mapa generado"
else
    echo "  WARN: project-mapper-simple no encontrado, saltando"
fi

# Generar AGENTS.md (punto de referencia hacia .agents)
"$PYTHON_BIN" "$SCRIPT_DIR/update_agents_md.py" --project "$PROJECT_ROOT" --sync

# Hacer ejecutable init.sh
if [ -f "$PROJECT_ROOT/.agents/init.sh" ]; then
    chmod +x "$PROJECT_ROOT/.agents/init.sh"
fi

echo ""
echo "=== Scaffolding completado para: $(basename "$PROJECT_ROOT") ==="
echo "  .opencode/config.json      → Configuración técnica"
echo "  .agents/rules/coding-rules.json → Reglas estructuradas"
echo "  .agents/rules/DESIGN.md    → Diseño y arquitectura"
echo "  AGENTS.md                  → Índice de referencia hacia .agents"
echo "  .agents/skills/            → Skills locales (project-mapper-simple, prompt-toolkit, agent-init)"
echo ""
echo "Personaliza .agents/rules/DESIGN.md con las reglas específicas de tu proyecto."