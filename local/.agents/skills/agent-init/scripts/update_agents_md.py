#!/usr/bin/env python3
"""Mantiene AGENTS.md como punto de referencia hacia la carpeta .agents del proyecto.

AGENTS.md NO documenta el proyecto: solo indica cómo actualizar .agents. Se regenera dentro de un bloque
delimitado por marcadores; lo que esté fuera del bloque se conserva.

Los hallazgos del agente se guardan en .agents/rules/LEARNINGS.md (no en AGENTS.md).
Solo se escribe lo que se pasa por argumento; no se infiere ni inventa contenido.

Uso:
  update_agents_md.py --project . --sync
  update_agents_md.py --category repetitive --text "Siempre correr npm run lint al terminar"
  update_agents_md.py --category error --text "El endpoint /api/x falla sin header Y"
  update_agents_md.py --category design --text "Botones primarios pasan a rounded-lg" \
      --rule-key styling.button_radius --rule-value '"rounded-lg"'

Categorías: repetitive | error | design
  - --rule-key/--rule-value: setea la clave (notación con puntos) en coding-rules.json.
  - category=design: además agrega la nota a la sección de cambios de diseño de DESIGN.md.
Siempre se vuelve a sincronizar el índice de AGENTS.md.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

START = "<!-- agent-init:start -->"
END = "<!-- agent-init:end -->"

SECTIONS = {
    "repetitive": "Patrones repetitivos",
    "error": "Errores conocidos de la app",
    "design": "Cambios de diseño",
}
LEARNINGS = "LEARNINGS.md"
DESIGN_HEADING = "## Cambios de diseño registrados"


# ---------- LEARNINGS.md ----------

def build_learnings(entries):
    lines = [
        "# Learnings del agente",
        "",
        "> Hallazgos registrados por `agent-init` (`update_agents_md.py`). "
        "Gestionado automáticamente; corregir o depurar entradas a mano es válido.",
    ]
    for key, title in SECTIONS.items():
        lines += ["", f"## {title}", ""]
        items = entries.get(key, [])
        lines += [f"- {i}" for i in items] if items else ["_Sin entradas._"]
    return "\n".join(lines) + "\n"


def parse_learnings(content):
    entries = {k: [] for k in SECTIONS}
    titles = {v: k for k, v in SECTIONS.items()}
    current = None
    for line in content.splitlines():
        if line.startswith("## "):
            current = titles.get(line[3:].strip())
        elif line.startswith("- ") and current:
            entries[current].append(line[2:].strip())
    return entries


def add_learning(rules_dir, category, text):
    path = rules_dir / LEARNINGS
    entries = parse_learnings(path.read_text(encoding="utf-8")) if path.exists() else {k: [] for k in SECTIONS}
    if text in entries[category]:
        return False
    entries[category].append(text)
    rules_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(build_learnings(entries), encoding="utf-8")
    return True


# ---------- Índice de .agents ----------

def build_index(root):
    return "\n".join([
        START,
        "# Actualizar `.agents/`",
        "",
        "Si detectás algo repetitivo, un error o un cambio de diseño, corregilo en `.agents/`:",
        "",
        "| Qué | Dónde |",
        "| :--- | :--- |",
        "| Reglas de estilo, nomenclatura o seguridad | `.agents/rules/coding-rules.json` |",
        "| Referencia de diseño | `.agents/rules/DESIGN.md` |",
        "| Repetitivo, error o cambio de diseño detectado | `.agents/rules/LEARNINGS.md` |",
        "| Una skill falla o está desactualizada | `.agents/skills/<skill>/SKILL.md` |",
        "",
        "Registrar con:",
        "`python3 .agents/skills/agent-init/scripts/update_agents_md.py --category <repetitive|error|design> --text \"...\"`",
        END,
    ])


def sync_agents_md(root):
    path = root / "AGENTS.md"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    block = build_index(root)
    s, e = content.find(START), content.find(END)
    if s != -1 and e > s:
        new = content[:s] + block + content[e + len(END):]
    elif content.strip():
        new = content.rstrip() + "\n\n" + block + "\n"
    else:
        new = block + "\n"
    path.write_text(new, encoding="utf-8")


# ---------- Reflejo en rules ----------

def set_rule(rules_path, key, value):
    if not rules_path.exists():
        print(f"WARN: {rules_path} no existe; no se actualizó coding-rules.json")
        return False
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    node = data
    parts = key.split(".")
    for p in parts[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    node[parts[-1]] = value
    rules_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def append_design(design_path, text):
    if not design_path.exists():
        print(f"WARN: {design_path} no existe; no se actualizó DESIGN.md")
        return False
    content = design_path.read_text(encoding="utf-8")
    if text in content:
        return False
    line = f"- {date.today().isoformat()}: {text}"
    if DESIGN_HEADING in content:
        head, _, tail = content.partition(DESIGN_HEADING)
        content = head + DESIGN_HEADING + "\n" + tail.rstrip("\n") + "\n" + line + "\n"
    else:
        content = content.rstrip("\n") + f"\n\n{DESIGN_HEADING}\n\n{line}\n"
    design_path.write_text(content, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", "-p", default=".")
    ap.add_argument("--sync", action="store_true", help="Solo regenerar el índice de AGENTS.md")
    ap.add_argument("--category", "-c", choices=list(SECTIONS))
    ap.add_argument("--text", "-t", help="Hallazgo a registrar (texto literal)")
    ap.add_argument("--rule-key", help="Clave con puntos en coding-rules.json (ej. styling.framework)")
    ap.add_argument("--rule-value", help="Valor JSON para --rule-key")
    args = ap.parse_args()

    if not args.sync and not (args.category and args.text):
        ap.error("usar --sync, o --category y --text juntos")
    if bool(args.rule_key) != bool(args.rule_value):
        ap.error("--rule-key y --rule-value deben usarse juntos")

    root = Path(args.project).resolve()
    rules = root / ".agents" / "rules"

    if args.category and args.text:
        text = args.text.strip()
        added = add_learning(rules, args.category, text)
        print(f"{LEARNINGS}: {'entrada agregada' if added else 'entrada ya existente'}")
        if args.rule_key:
            try:
                value = json.loads(args.rule_value)
            except json.JSONDecodeError:
                print("ERROR: --rule-value no es JSON válido", file=sys.stderr)
                sys.exit(1)
            if set_rule(rules / "coding-rules.json", args.rule_key, value):
                print(f"coding-rules.json: {args.rule_key} actualizado")
        if args.category == "design" and append_design(rules / "DESIGN.md", text):
            print("DESIGN.md: cambio de diseño registrado")

    sync_agents_md(root)
    print("AGENTS.md: índice de .agents sincronizado")


if __name__ == "__main__":
    main()
