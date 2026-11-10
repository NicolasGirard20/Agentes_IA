#!/usr/bin/env python3
"""Detecta el stack tecnológico de un proyecto leyendo package.json y archivos de configuración."""

import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def read_json(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return json.load(f)


def detect_dotnet(project_root):
    try:
        files = os.listdir(project_root)
    except Exception:
        files = []
        
    has_csproj = any(f.endswith(".csproj") for f in files)
    has_sln = any(f.endswith(".sln") for f in files)
    has_web_config = "Web.config" in files
    has_packages_config = "packages.config" in files
    
    if not (has_csproj or has_sln or has_web_config or has_packages_config):
        return None
        
    project_name = os.path.basename(os.path.abspath(project_root))
    for f in files:
        if f.endswith(".csproj"):
            project_name = os.path.splitext(f)[0]
            break
            
    stack = {
        "project_name": project_name,
        "language": "csharp",
        "framework": "dotnet-mvc",
        "runtime": ".NET Framework 4.8",
        "orm": "entity-framework",
        "styling": "bootstrap",
        "ui_library": "bootstrap",
        "icon_library": "bootstrap-icons",
        "view_engine": "razor",
        "auth": "aspnet-identity",
        "testing": None,
    }
    
    if has_packages_config:
        try:
            with open(os.path.join(project_root, "packages.config"), "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "Microsoft.AspNet.Mvc" in content:
                    stack["framework"] = "dotnet-mvc"
                if "EntityFramework" in content:
                    stack["orm"] = "entity-framework"
                if "bootstrap" in content:
                    stack["styling"] = "bootstrap"
                if "Microsoft.AspNet.Identity" in content:
                    stack["auth"] = "aspnet-identity"
        except Exception:
            pass
            
    stack["has_dedicated_template"] = True
    stack["needs_context7"] = False
    stack["context7_candidates"] = []
    return stack


def _build_context7_candidates(stack, raw_deps=None):
    """Construye la lista de librerías candidatas para consultar en MCP Context7."""
    candidates = []
    fw_names = {
        "nextjs": "Next.js",
        "remix": "Remix",
        "react-vite": "React",
        "react": "React",
        "svelte": "SvelteKit" if stack.get("sveltekit") else "Svelte",
        "astro": "Astro",
        "solid": "SolidJS",
        "nuxt": "Nuxt",
        "vue": "Vue.js",
        "angular": "Angular",
        "nestjs": "NestJS",
        "express": "Express",
        "fastify": "Fastify",
        "hono": "Hono",
        "expo": "Expo",
        "react-native": "React Native",
        "electron": "Electron",
        "qwik": "Qwik",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "laravel": "Laravel",
        "spring-boot": "Spring Boot",
    }
    fw = stack.get("framework", "unknown")
    if fw in fw_names:
        candidates.append({
            "libraryName": fw_names[fw],
            "role": "framework",
            "query": f"{fw_names[fw]} project structure architecture conventions best practices routing"
        })
    elif raw_deps:
        # Si el framework es desconocido pero hay dependencias, tomar las principales
        ignored = {"typescript", "eslint", "prettier", "nodemon", "ts-node", "tsx", "rimraf", "dotenv"}
        for dep in list(raw_deps.keys()):
            clean = dep.lower()
            if clean not in ignored and not clean.startswith("@types/"):
                candidates.append({
                    "libraryName": dep,
                    "role": "dependency",
                    "query": f"{dep} project structure conventions best practices configuration"
                })
                if len(candidates) >= 2:
                    break

    for role in ("orm", "ui_library", "styling", "auth"):
        val = stack.get(role)
        if val and val not in ("unknown", "none", None):
            candidates.append({
                "libraryName": val,
                "role": role,
                "query": f"{val} best practices configuration folder structure patterns"
            })

    return candidates


def detect_non_node(project_root):
    """Detecta proyectos Python, Go, Rust, PHP o Java cuando no existe package.json."""
    project_name = os.path.basename(os.path.abspath(project_root))
    base = {
        "project_name": project_name,
        "language": "unknown",
        "framework": "unknown",
        "orm": None,
        "styling": None,
        "ui_library": None,
        "auth": None,
        "testing": None,
        "has_dedicated_template": False,
        "needs_context7": True,
        "context7_candidates": [],
    }

    # Python (pyproject.toml / requirements.txt)
    req_files = ["pyproject.toml", "requirements.txt", "Pipfile"]
    py_content = ""
    for rf in req_files:
        p = os.path.join(project_root, rf)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    py_content += "\n" + f.read().lower()
            except Exception:
                pass
    if py_content:
        base["language"] = "python"
        if "fastapi" in py_content:
            base["framework"] = "fastapi"
        elif "django" in py_content:
            base["framework"] = "django"
        elif "flask" in py_content:
            base["framework"] = "flask"
        else:
            base["framework"] = "python"
        if "sqlalchemy" in py_content or "sqlmodel" in py_content:
            base["orm"] = "sqlalchemy"
        elif "tortoise" in py_content:
            base["orm"] = "tortoise-orm"
        if "pytest" in py_content:
            base["testing"] = "pytest"
        base["context7_candidates"] = _build_context7_candidates(base)
        return base

    # Go
    if os.path.exists(os.path.join(project_root, "go.mod")):
        base["language"] = "go"
        base["framework"] = "go"
        base["context7_candidates"] = [{"libraryName": "Go", "role": "framework", "query": "Go project layout standard structure best practices"}]
        return base

    # Rust
    if os.path.exists(os.path.join(project_root, "Cargo.toml")):
        base["language"] = "rust"
        base["framework"] = "rust"
        base["context7_candidates"] = [{"libraryName": "Rust", "role": "framework", "query": "Rust Cargo project structure modules conventions"}]
        return base

    # PHP / Laravel
    composer_path = os.path.join(project_root, "composer.json")
    if os.path.exists(composer_path):
        base["language"] = "php"
        try:
            comp = read_json(composer_path)
            deps_str = json.dumps(comp.get("require", {})).lower()
            base["framework"] = "laravel" if "laravel" in deps_str else "php"
        except Exception:
            base["framework"] = "php"
        base["context7_candidates"] = _build_context7_candidates(base)
        return base

    return None


def detect_stack(project_root):
    dotnet_stack = detect_dotnet(project_root)
    if dotnet_stack:
        return dotnet_stack

    pkg_path = os.path.join(project_root, "package.json")
    if not os.path.exists(pkg_path):
        non_node = detect_non_node(project_root)
        if non_node:
            return non_node
        return {
            "error": "package.json o archivo de proyecto no encontrado",
            "framework": "unknown",
            "has_dedicated_template": False,
            "needs_context7": True,
            "context7_candidates": [],
        }

    pkg = read_json(pkg_path)
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    all_deps_lower = {k.lower(): v for k, v in deps.items()}

    stack = {
        "project_name": pkg.get("name", os.path.basename(project_root)),
        "language": "typescript" if any("typescript" in k for k in all_deps_lower) else "javascript",
        "framework": "unknown",
        "orm": None,
        "styling": None,
        "ui_library": None,
        "auth": None,
        "testing": None,
        "has_app_router": False,
        "has_pages_router": False,
    }

    if "next" in all_deps_lower:
        stack["framework"] = "nextjs"
        try:
            next_config = read_json(os.path.join(project_root, "next.config.json")) if os.path.exists(os.path.join(project_root, "next.config.json")) else {}
            if os.path.exists(os.path.join(project_root, "next.config.js")) or os.path.exists(os.path.join(project_root, "next.config.mjs")):
                pass
        except Exception:
            pass
        if os.path.exists(os.path.join(project_root, "src", "app")):
            stack["has_app_router"] = True
        if os.path.exists(os.path.join(project_root, "src", "pages")) or os.path.exists(os.path.join(project_root, "pages")):
            stack["has_pages_router"] = True
    elif "@remix-run" in str(all_deps_lower) or "remix" in all_deps_lower:
        stack["framework"] = "remix"
    elif "expo" in all_deps_lower:
        stack["framework"] = "expo"
    elif "react-native" in all_deps_lower:
        stack["framework"] = "react-native"
    elif "react" in all_deps_lower:
        if "vite" in all_deps_lower:
            stack["framework"] = "react-vite"
        else:
            stack["framework"] = "react"
    elif "@sveltejs/kit" in all_deps_lower or "sveltekit" in all_deps_lower:
        stack["framework"] = "svelte"
        stack["sveltekit"] = True
    elif "svelte" in all_deps_lower:
        stack["framework"] = "svelte"
    elif "astro" in all_deps_lower:
        stack["framework"] = "astro"
    elif "solid-start" in all_deps_lower or "@solidjs/start" in all_deps_lower:
        stack["framework"] = "solid"
    elif "solid" in all_deps_lower or "@solidjs/core" in all_deps_lower:
        stack["framework"] = "solid"
    elif "nuxt" in all_deps_lower or "@nuxt/core" in all_deps_lower:
        stack["framework"] = "nuxt"
    elif "vue" in all_deps_lower:
        if "nuxt" in all_deps_lower:
            stack["framework"] = "nuxt"
        else:
            stack["framework"] = "vue"
    elif "angular" in all_deps_lower or "@angular/core" in all_deps_lower:
        stack["framework"] = "angular"
    elif "@nestjs/core" in all_deps_lower or "nestjs" in str(all_deps_lower):
        stack["framework"] = "nestjs"
    elif "fastify" in all_deps_lower:
        stack["framework"] = "fastify"
    elif "hono" in all_deps_lower:
        stack["framework"] = "hono"
    elif "express" in all_deps_lower:
        stack["framework"] = "express"
    elif "electron" in all_deps_lower:
        stack["framework"] = "electron"
    elif "@builder.io/qwik" in all_deps_lower:
        stack["framework"] = "qwik"

    if "prisma" in all_deps_lower or "@prisma/client" in all_deps_lower:
        stack["orm"] = "prisma"
        if os.path.exists(os.path.join(project_root, "prisma", "schema.prisma")):
            stack["prisma_schema"] = "prisma/schema.prisma"
    elif "drizzle-orm" in all_deps_lower:
        stack["orm"] = "drizzle"
    elif "typeorm" in all_deps_lower:
        stack["orm"] = "typeorm"
    elif "mongoose" in all_deps_lower:
        stack["orm"] = "mongoose"
    elif "sequelize" in all_deps_lower:
        stack["orm"] = "sequelize"

    if "tailwindcss" in all_deps_lower:
        stack["styling"] = "tailwindcss"
    elif "styled-components" in all_deps_lower:
        stack["styling"] = "styled-components"
    elif "@emotion/react" in all_deps_lower:
        stack["styling"] = "emotion"
    elif "sass" in all_deps_lower or "node-sass" in all_deps_lower:
        stack["styling"] = "sass"

    if "@radix-ui" in str(all_deps_lower) or "radix-ui" in str(all_deps_lower):
        stack["ui_library"] = "radix-ui"
    elif "@shadcn" in str(all_deps_lower) or "shadcn" in str(all_deps_lower):
        stack["ui_library"] = "shadcn"
    elif "antd" in all_deps_lower or "@ant-design" in str(all_deps_lower):
        stack["ui_library"] = "ant-design"
    elif "@mui" in str(all_deps_lower) or "@material-ui" in str(all_deps_lower):
        stack["ui_library"] = "material-ui"
    elif "chakra" in all_deps_lower or "@chakra-ui" in str(all_deps_lower):
        stack["ui_library"] = "chakra-ui"

    if "next-auth" in all_deps_lower or "next-auth" in str(all_deps_lower):
        stack["auth"] = "next-auth"
    elif "clerk" in str(all_deps_lower):
        stack["auth"] = "clerk"
    elif "jose" in all_deps_lower:
        stack["auth"] = "jwt-custom"
    elif "bcrypt" in all_deps_lower or "bcryptjs" in all_deps_lower:
        if not stack["auth"]:
            stack["auth"] = "custom-hashed"

    if "jest" in all_deps_lower:
        stack["testing"] = "jest"
    elif "vitest" in all_deps_lower:
        stack["testing"] = "vitest"
    elif "@testing-library" in str(all_deps_lower):
        stack["testing"] = "testing-library"

    has_dedicated = (
        stack["framework"] in ("dotnet-mvc", "aspnet-mvc", "react-vite", "react")
        or (stack["framework"] == "nextjs" and stack["orm"] == "prisma")
    )
    stack["has_dedicated_template"] = has_dedicated
    stack["needs_context7"] = not has_dedicated
    stack["context7_candidates"] = _build_context7_candidates(stack, deps) if not has_dedicated else []

    return stack


if __name__ == "__main__":
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    stack = detect_stack(project_root)
    print(json.dumps(stack, indent=2))