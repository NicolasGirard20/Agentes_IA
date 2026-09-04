#!/usr/bin/env python3
"""
init.py — Inicializador universal multiplataforma de agentes para Antigravity.
Ejecutable directamente en Windows, macOS y Linux sin requerir bash ni dependencias externas.
"""
import os
import sys
import json
import subprocess
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_NAME = PROJECT_ROOT.name
MAPPER_RESOURCES = PROJECT_ROOT / ".agents" / "skills" / "project-mapper" / "resources"
MAP_FILE = MAPPER_RESOURCES / "project_map.json"
CONFIG_FILE = PROJECT_ROOT / ".opencode" / "config.json"

print(f"=== Inicialización de Agente — {PROJECT_NAME} ===")

# 1. Scaffolding inicial si no existe config.json
if not CONFIG_FILE.exists():
    print("Configuración no encontrada. Ejecutando scaffolding inicial...")
    detect_script = PROJECT_ROOT / ".agents" / "skills" / "agent-init" / "scripts" / "detect_stack.py"
    config_script = PROJECT_ROOT / ".agents" / "skills" / "agent-init" / "scripts" / "generate_config.py"
    rules_script = PROJECT_ROOT / ".agents" / "skills" / "agent-init" / "scripts" / "scaffold_rules.py"
    
    if detect_script.exists():
        proc = subprocess.run([sys.executable, str(detect_script), str(PROJECT_ROOT)], capture_output=True, text=True, encoding="utf-8")
        stack_json = proc.stdout
        subprocess.run([sys.executable, str(config_script), str(PROJECT_ROOT)], input=stack_json, text=True, encoding="utf-8")
        subprocess.run([sys.executable, str(rules_script), str(PROJECT_ROOT)], input=stack_json, text=True, encoding="utf-8")
    else:
        print("WARN: agent-init no encontrado. Saltando scaffolding.")

# 2. Verificar project-mapper
generate_map_script = PROJECT_ROOT / ".agents" / "skills" / "project-mapper" / "scripts" / "generate_map.py"
if not generate_map_script.exists():
    print("ERROR: project-mapper no encontrado localmente")
    sys.exit(1)

# 3. Generar mapa si no existe o tiene más de 2 horas (7200 segundos)
regenerate = True
if MAP_FILE.exists():
    try:
        mtime = MAP_FILE.stat().st_mtime
        with MAP_FILE.open("r", encoding="utf-8") as map_file:
            existing_map = json.load(map_file)
        map_is_valid = isinstance(existing_map, dict) and bool(existing_map.get("generated_at"))
        if map_is_valid and (time.time() - mtime) < 7200:
            regenerate = False
    except Exception:
        regenerate = True

if regenerate:
    print("Regenerando mapa del proyecto...")
    MAPPER_RESOURCES.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(generate_map_script),
        "--project", str(PROJECT_ROOT),
        "--output", str(MAP_FILE),
        "--force"
    ])
else:
    print("Mapa reciente encontrado (< 2 horas). Saltando generación.")

# 4. Validar prompt-toolkit
validator_rules = PROJECT_ROOT / ".agents" / "skills" / "prompt-toolkit" / "validator" / "rules.json"
if not validator_rules.exists():
    print("WARN: prompt-toolkit validator no encontrado")

print("=== Listo ===")
