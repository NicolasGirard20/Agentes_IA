#!/usr/bin/env python3
"""Genera coding-rules.json y DESIGN.md para frameworks sin template dedicado.

Recibe el stack detectado por detect_stack.py por stdin y genera
.agents/rules/coding-rules.json y .agents/rules/DESIGN.md.
Si el framework no está en el diccionario, genera reglas genéricas.
"""

import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def _base_rules(stack, project_root):
    lang = stack.get("language", "typescript")
    styling = stack.get("styling", "unknown")
    ui_lib = stack.get("ui_library", "unknown")
    orm = stack.get("orm", None)
    auth = stack.get("auth", None)

    rules = {
        "project": stack.get("project_name", os.path.basename(project_root)),
        "typescript": {
            "strict": lang == "typescript",
            "forbid_any": lang == "typescript",
            "forbid_deep_relative_imports": True,
            "prefer_path_alias": True
        },
        "nomenclature": {
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "styling": {
            "framework": styling,
            "forbid_inline_styles": True,
            "ui_library": ui_lib
        },
        "architecture": {},
        "security": {
            "forbid_secrets_in_code": True,
            "forbid_passwords_in_logs": True,
            "validate_inputs_before_persist": True
        },
        "code_quality": {
            "lint_before_finish": True,
            "lint_command": "npm run lint",
            "no_new_deps_without_justification": True
        }
    }

    if auth:
        rules["security"]["auth_type"] = auth
        rules["security"]["auth_required_pages"] = auth != "none"

    if orm:
        rules["architecture"]["orm"] = orm
        rules["security"]["queries_via_orm_only"] = True

    return rules


FRAMEWORK_RULES = {
    "angular": {
        "nomenclature": {
            "components": "*.component.ts",
            "services": "*.service.ts",
            "modules": "*.module.ts",
            "guards": "*.guard.ts",
            "pipes": "*.pipe.ts",
            "directives": "*.directive.ts",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "components_path": "src/app/components/",
            "services_path": "src/app/services/",
            "guards_path": "src/app/guards/",
            "models_path": "src/app/models/",
            "standalone_components": True,
            "dependency_injection": True,
            "reactive_forms": True
        },
        "angular": {
            "standalone_by_default": True,
            "use_rxjs_operators": True,
            "on_push_change_detection": True,
            "forbid_any_in_services": True
        }
    },
    "vue": {
        "nomenclature": {
            "components": "PascalCase.vue",
            "composables": "use*.ts",
            "stores": "*.store.ts",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "components_path": "src/components/",
            "composables_path": "src/composables/",
            "stores_path": "src/stores/",
            "views_path": "src/views/"
        },
        "vue": {
            "composition_api": True,
            "script_setup": True,
            "state_library": "pinia",
            "forbid_options_api": True
        }
    },
    "nuxt": {
        "nomenclature": {
            "components": "PascalCase.vue",
            "pages": "camelCase.vue",
            "composables": "use*.ts",
            "stores": "*.store.ts",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "pages_path": "pages/",
            "components_path": "components/",
            "composables_path": "composables/",
            "stores_path": "stores/",
            "layouts_path": "layouts/"
        },
        "nuxt": {
            "auto_imports": True,
            "composition_api": True,
            "state_library": "pinia"
        }
    },
    "svelte": {
        "nomenclature": {
            "components": "PascalCase.svelte",
            "stores": "*.store.ts",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "components_path": "src/lib/components/",
            "stores_path": "src/lib/stores/",
            "routes_path": "src/routes/"
        },
        "svelte": {
            "runes_by_default": True,
            "stores_for_shared_state": True,
            "forbid_any_in_stores": True
        }
    },
    "astro": {
        "nomenclature": {
            "components": "PascalCase.astro",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "components_path": "src/components/",
            "layouts_path": "src/layouts/",
            "pages_path": "src/pages/",
            "islands_architecture": True
        },
        "astro": {
            "islands_by_default": True,
            "content_collections": True,
            "minimal_client_js": True
        }
    },
    "solid": {
        "nomenclature": {
            "components": "PascalCase.tsx",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "components_path": "src/components/",
            "routes_path": "src/routes/"
        },
        "solid": {
            "signals_for_state": True,
            "forbid_class_components": True,
            "render_once_by_default": True
        }
    },
    "remix": {
        "nomenclature": {
            "components": "PascalCase.tsx",
            "routes": "camelCase.tsx",
            "folders": "kebab-case",
            "code_language": "en",
            "ui_language": "es"
        },
        "architecture": {
            "routes_path": "app/routes/",
            "components_path": "app/components/",
            "services_path": "app/services/"
        },
        "remix": {
            "loaders_for_data": True,
            "actions_for_mutations": True,
            "server_components_by_default": True
        }
    }
}


def _load_context7_data(project_root, stack, explicit_path=None):
    """Carga datos obtenidos desde el MCP Context7 si están disponibles."""
    if isinstance(stack.get("context7"), dict) and stack["context7"]:
        return stack["context7"]

    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    candidates.append(os.path.join(project_root, ".agents", "rules", ".context7_cache.json"))

    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
            except Exception:
                pass
    return None


def _apply_context7_overlay(rules, framework, c7_data):
    """Aplica las reglas y convenciones consultadas en MCP Context7 sobre las reglas base."""
    rules["source"] = "context7"
    if "libraries" in c7_data and isinstance(c7_data["libraries"], list):
        rules["context7_libraries"] = c7_data["libraries"]
    elif "library_id" in c7_data:
        rules["context7_libraries"] = [c7_data["library_id"]]

    for section in ("nomenclature", "architecture", "styling", "security", "code_quality"):
        if isinstance(c7_data.get(section), dict):
            rules.setdefault(section, {}).update(c7_data[section])

    fw_key = c7_data.get("framework_key") or (framework if framework != "unknown" else None)
    if fw_key and isinstance(c7_data.get("framework_rules"), dict):
        rules.setdefault(fw_key, {}).update(c7_data["framework_rules"])
    elif fw_key and isinstance(c7_data.get(fw_key), dict):
        rules.setdefault(fw_key, {}).update(c7_data[fw_key])

    if isinstance(c7_data.get("conventions"), list) and c7_data["conventions"]:
        rules["architecture"]["context7_conventions"] = c7_data["conventions"]

    rules["architecture"].pop("generic_fallback", None)
    return rules


def generate_framework_rules(stack, project_root, context7_data=None):
    framework = stack.get("framework", "unknown")
    rules = _base_rules(stack, project_root)

    if framework in FRAMEWORK_RULES:
        fw = FRAMEWORK_RULES[framework]
        rules["nomenclature"].update(fw.get("nomenclature", {}))
        rules["architecture"].update(fw.get("architecture", {}))
        rules[framework] = dict(fw.get(framework, {}))
        rules["source"] = "framework_fallback"
    else:
        rules["nomenclature"].setdefault("components", "PascalCase.tsx")
        rules["nomenclature"].setdefault("services", "camelCase.ts")
        rules["architecture"]["generic_fallback"] = True
        rules["source"] = "generic_fallback"

    if context7_data:
        rules = _apply_context7_overlay(rules, framework, context7_data)

    return rules


if __name__ == "__main__":
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(description="Genera coding-rules.json y DESIGN.md (con soporte MCP Context7)")
    parser.add_argument("project_root", nargs="?", default=".", help="Ruta raíz del proyecto")
    parser.add_argument("--context7-file", dest="context7_file", default=None, help="JSON con reglas obtenidas de MCP Context7")
    args = parser.parse_args()

    project_root = args.project_root
    stack_input = sys.stdin.read() if not sys.stdin.isatty() else "{}"
    stack = json.loads(stack_input) if stack_input.strip() else {}

    c7_data = _load_context7_data(project_root, stack, args.context7_file)
    if c7_data:
        stack["context7"] = c7_data

    rules = generate_framework_rules(stack, project_root, context7_data=c7_data)

    rules_dir = os.path.join(project_root, ".agents", "rules")
    os.makedirs(rules_dir, exist_ok=True)

    with open(os.path.join(rules_dir, "coding-rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    origin_label = "MCP Context7" if c7_data else f"fallback ({rules.get('source', 'generic')})"
    print(f"coding-rules.json generado ({origin_label})")

    design_script = os.path.join(os.path.dirname(__file__), "generate_design.py")
    subprocess.run(
        [sys.executable, design_script, project_root],
        input=json.dumps(stack),
        text=True,
        check=True,
    )