#!/usr/bin/env python3
"""Generate a rich, modular structural map of a source project.

Pure Python stdlib (dependency-free). Supports Python, JavaScript/TypeScript,
C# (.cs), Razor/HTML (.cshtml/.html), SQL (.sql), PowerShell (.ps1), Markdown,
and XML/JSON configuration files.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from extractors import build_summary_and_context, extract_file_info, infer_role

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".cs": "csharp",
    ".cshtml": "razor",
    ".html": "html",
    ".htm": "html",
    ".sql": "sql",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".md": "markdown",
    ".config": "xml",
    ".xml": "xml",
    ".json": "json",
    ".css": "css",
    ".scss": "css",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".c": "c",
    ".swift": "swift",
}


class FileWalker:
    """Walk source files while applying default and user glob exclusions."""

    DEFAULT_EXCLUDES = {
        ".git/**", ".venv/**", "venv/**", "node_modules/**", "__pycache__/**",
        ".pytest_cache/**", "dist/**", "build/**", ".next/**", "out/**",
        "coverage/**", "target/**", "vendor/**", "packages/**", "bin/**", "obj/**",
        ".vs/**", ".idea/**", ".vscode/**", ".agents/**", ".opencode/**",
        "**/*.min.js", "**/*.min.css", "**/*.map",
        "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
        "bun.lockb", "*.tsbuildinfo", "*.pyc", "*.pyo", "*.so", "*.dll",
        "*.dylib", "*.exe", "*.pdb", "*.nupkg", "*.xdt", "*.transform",
        "*.user", "*.suo", "*.cache", "*.png", "*.jpg", "*.jpeg", "*.gif",
        "*.webp", "*.ico", "*.svg", "*.woff", "*.woff2", "*.ttf", "*.otf",
        "*.eot", "*.mp3", "*.mp4", "*.webm", "*.zip", "*.tar", "*.gz",
        "*.rar", "*.7z", "*.pdf", "*.log", ".env", ".env.*", ".DS_Store",
        "Thumbs.db",
    }

    def __init__(self, project_path: Path, excludes: Sequence[str]):
        self.project_path = project_path.resolve()
        self.excludes = set(self.DEFAULT_EXCLUDES) | set(excludes)

    def ignored(self, path: Path) -> bool:
        relative = path.relative_to(self.project_path).as_posix()
        return any(
            fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern)
            for pattern in self.excludes
        )

    def files(self) -> Iterable[Path]:
        for root, dirs, names in os.walk(self.project_path):
            root_path = Path(root)
            dirs[:] = [
                name
                for name in dirs
                if not name.startswith(".") and not self.ignored(root_path / name)
            ]
            for name in names:
                path = root_path / name
                if not self.ignored(path) and path.is_file():
                    try:
                        if path.stat().st_size <= 2_000_000:
                            yield path
                    except OSError:
                        continue


class DependencyGraph:
    """Resolve local JS/TS, Python, C#, and Razor/MVC dependencies."""

    JS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
    PY_EXTENSIONS = (".py",)

    def __init__(self, project_path: Path, files: Sequence[Dict[str, Any]]):
        self.project_path = project_path
        self.files = {item["path"] for item in files}
        self.files_lower = {p.lower(): p for p in self.files}
        self.aliases = self._load_aliases()
        self.class_to_files: Dict[str, List[str]] = {}
        self.partial_to_files: Dict[str, List[str]] = {}

        for item in files:
            path = item["path"]
            for cls in item.get("classes", []):
                name = cls.get("name") if isinstance(cls, dict) else cls
                if name:
                    self.class_to_files.setdefault(name, []).append(path)
            if path.endswith(".cshtml"):
                stem = Path(path).stem
                self.partial_to_files.setdefault(stem.lower(), []).append(path)

    def _load_aliases(self) -> Dict[str, List[str]]:
        aliases: Dict[str, List[str]] = {}
        for config_name in ("tsconfig.json", "jsconfig.json"):
            config_path = self.project_path / config_name
            if not config_path.exists():
                continue
            try:
                raw = re.sub(
                    r"/\*.*?\*/|//.*?$",
                    "",
                    config_path.read_text(encoding="utf-8"),
                    flags=re.MULTILINE | re.DOTALL,
                )
                config = json.loads(raw)
                options = config.get("compilerOptions", {})
                base = Path(options.get("baseUrl", "."))
                for key, targets in options.get("paths", {}).items():
                    aliases[key.rstrip("*")] = [str(base / target.rstrip("*")) for target in targets]
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        return aliases

    def _candidates(self, source: str, importer: str) -> Iterable[str]:
        roots: List[str] = []
        if source.startswith("@/"):
            aliased = source[2:]
            roots.extend((aliased, str(Path("src") / aliased)))
        else:
            for alias, targets in self.aliases.items():
                if source.startswith(alias):
                    roots.extend(target + source[len(alias) :] for target in targets)
            if source.startswith("."):
                level = len(source) - len(source.lstrip("."))
                parent = Path(importer).parent
                for _ in range(max(level - 1, 0)):
                    parent = parent.parent
                roots.append(str(parent / source[level:]))
            elif not roots:
                return
        for root in roots:
            root = root.replace("\\", "/")
            for extension in self.JS_EXTENSIONS + self.PY_EXTENSIONS + ("",):
                candidate = Path(root).with_suffix(extension) if extension else Path(root)
                yield candidate.as_posix()
                yield (Path(root) / ("index" + extension)).as_posix()
                yield (Path(root) / ("__init__" + extension)).as_posix()

    def _resolve_web_or_mvc_ref(self, ref: str, importer: str) -> List[str]:
        resolved: List[str] = []
        cleaned = ref.split("?")[0].split("#")[0].strip()
        if not cleaned or cleaned.startswith(("http://", "https://", "//")):
            return resolved

        if cleaned.startswith("~/"):
            rel = cleaned[2:].lstrip("/")
            if rel in self.files:
                resolved.append(rel)
            elif rel.lower() in self.files_lower:
                resolved.append(self.files_lower[rel.lower()])
        elif cleaned.endswith((".js", ".css", ".cshtml")):
            rel = cleaned.lstrip("/")
            if rel in self.files:
                resolved.append(rel)
            elif rel.lower() in self.files_lower:
                resolved.append(self.files_lower[rel.lower()])
            else:
                same_dir = (Path(importer).parent / Path(rel).name).as_posix()
                if same_dir in self.files:
                    resolved.append(same_dir)

        # Razor partial name without extension (e.g. "_RegistrarHistorialClinicoMascota")
        stem = Path(cleaned).stem.lower()
        if importer.endswith(".cshtml") and stem in self.partial_to_files:
            for cand in self.partial_to_files[stem]:
                if cand != importer:
                    resolved.append(cand)

        # Controller name from Url.Action / BeginForm
        ctrl_candidate = f"Controllers/{cleaned}Controller.cs"
        if ctrl_candidate in self.files:
            resolved.append(ctrl_candidate)
        elif ctrl_candidate.lower() in self.files_lower:
            resolved.append(self.files_lower[ctrl_candidate.lower()])

        # C# class/model/service/DAO name
        if cleaned in self.class_to_files:
            for cand in self.class_to_files[cleaned]:
                if cand != importer:
                    resolved.append(cand)

        return resolved

    def build(self, files: Sequence[Dict[str, Any]], refs_by_file: Dict[str, List[str]]) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for item in files:
            path = item["path"]
            deps: Set[str] = set()
            for source in item.get("imports", []):
                for candidate in self._candidates(source, path):
                    if candidate in self.files and candidate != path:
                        deps.add(candidate)
                        break

            for ref in refs_by_file.get(path, []):
                for target in self._resolve_web_or_mvc_ref(ref, path):
                    if target != path:
                        deps.add(target)

            # Link Views/<Controller>/<Action>.cshtml -> Controllers/<Controller>Controller.cs
            if path.startswith("Views/") and path.endswith(".cshtml"):
                parts = Path(path).parts
                if len(parts) >= 3 and parts[1].lower() != "shared":
                    ctrl = f"Controllers/{parts[1]}Controller.cs"
                    if ctrl in self.files:
                        deps.add(ctrl)
                    elif ctrl.lower() in self.files_lower:
                        deps.add(self.files_lower[ctrl.lower()])

            graph[path] = sorted(deps)
        return graph


class ProjectMapper:
    """Coordinate walking, modular language extraction, graph building, and output."""

    ENTRY_FILENAMES = {
        "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py", "cli.py",
        "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
        "program.cs", "startup.cs", "global.asax.cs", "global.asax",
    }

    def __init__(
        self,
        project_path: Path,
        include_lines: bool = False,
        light: bool = False,
        excludes: Sequence[str] = (),
    ):
        self.project_path = project_path.resolve()
        self.include_lines = include_lines
        self.light = light
        self.walker = FileWalker(self.project_path, excludes)
        self.entry_points: List[str] = []

    def _check_entry_point(self, path: Path) -> None:
        if path.name.lower() in self.ENTRY_FILENAMES:
            self.entry_points.append(path.relative_to(self.project_path).as_posix())

    def _architecture(self, files: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        directories = sorted(
            {Path(item["path"]).parts[0] for item in files if len(Path(item["path"]).parts) > 1}
        )
        groups = {
            "core_modules": [],
            "utils": [],
            "tests": [],
            "config": [],
            "infrastructure": [],
        }
        for directory in directories:
            name = directory.lower()
            if any(
                token in name
                for token in (
                    "src", "app", "lib", "core", "module", "component", "package",
                    "controller", "service", "dao", "model", "viewmodel", "view", "filter",
                )
            ):
                groups["core_modules"].append(directory)
            elif any(token in name for token in ("test", "spec", "e2e")):
                groups["tests"].append(directory)
            elif any(token in name for token in ("util", "helper", "tool", "script", "shared", "common", "content")):
                groups["utils"].append(directory)
            elif any(token in name for token in ("config", "setting", "env", "docker", "k8s", "app_start")):
                groups["config"].append(directory)
            elif any(token in name for token in ("infra", "deploy", "terraform", "ansible")):
                groups["infrastructure"].append(directory)
        return {
            "entry_points": sorted(self.entry_points) or ["(detectar manualmente)"],
            **groups,
            "all_directories": directories,
        }

    def generate_map(self) -> Dict[str, Any]:
        files: List[Dict[str, Any]] = []
        refs_by_file: Dict[str, List[str]] = {}
        total_symbols = 0

        for path in self.walker.files():
            try:
                content = path.read_text(encoding="utf-8-sig", errors="ignore")
            except OSError:
                continue

            rel_path = path.relative_to(self.project_path).as_posix()
            language = LANGUAGE_MAP.get(path.suffix.lower(), "unknown")
            self._check_entry_point(path)

            extracted = extract_file_info(content, path, language, self.include_lines)
            role = infer_role(rel_path, language, extracted)
            summary, context, keywords = build_summary_and_context(rel_path, language, extracted, role)

            classes = extracted.get("classes", [])
            functions = extracted.get("functions", [])
            total_symbols += len(classes) + len(functions)
            line_count = len(content.splitlines())
            complexity = "low" if line_count < 30 else "medium" if line_count < 100 else "high"

            refs_by_file[rel_path] = extracted.get("references", [])

            item: Dict[str, Any] = {
                "path": rel_path,
                "language": language,
                "role": role,
                "size_lines": line_count,
                "summary": summary,
                "context": context,
                "keywords": keywords,
                "imports": sorted(set(extracted.get("imports", []))),
                "exports": sorted(set(extracted.get("exports", []))),
                "classes": classes,
                "functions": functions,
                "complexity": complexity,
            }
            if self.light:
                item = {
                    key: item[key]
                    for key in ("path", "summary", "imports", "exports", "complexity")
                }
            files.append(item)

        files.sort(key=lambda item: item["path"])
        graph = DependencyGraph(self.project_path, files).build(files, refs_by_file)
        return {
            "project_name": self.project_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_files": len(files),
            "total_symbols": total_symbols,
            "architecture": self._architecture(files),
            "files": files,
            "dependency_graph": graph,
            "metadata": {
                "mapper_version": "4.0.0",
                "languages_found": sorted(set(item.get("language", "unknown") for item in files)),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Project Mapper para Antigravity")
    parser.add_argument("--project", "-p", default=".", help="Ruta al proyecto")
    parser.add_argument("--output", "-o", required=True, help="Ruta de salida del JSON")
    parser.add_argument("--force", "-f", action="store_true", help="Forzar regeneración")
    parser.add_argument("--max-age-hours", type=float, default=2.0)
    parser.add_argument("--light", action="store_true", help="Solo path, summary, imports, exports y complexity")
    parser.add_argument("--include-lines", action="store_true", help="Incluir líneas en clases y funciones")
    parser.add_argument("--exclude", action="append", default=[], help="Patrón glob adicional a ignorar; se puede repetir")
    args = parser.parse_args()
    project_path, output_path = Path(args.project).resolve(), Path(args.output).resolve()

    if not args.force and output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            generated = datetime.fromisoformat(existing["generated_at"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - generated).total_seconds() / 3600 < args.max_age_hours:
                print(f"Mapa reciente ({output_path}); use --force para regenerar.")
                return
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

    project_map = ProjectMapper(project_path, args.include_lines, args.light, args.exclude).generate_map()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(project_map, indent=2, ensure_ascii=False)
    output_path.write_text(serialized + "\n", encoding="utf-8")
    size_kb = len((serialized + "\n").encode("utf-8")) / 1024
    estimated_tokens = len(serialized) // 4
    print(f"Mapa generado: {output_path}")
    print(f"Archivos procesados: {project_map['total_files']}")
    print(f"Símbolos reales detectados: {project_map['total_symbols']}")
    print(f"Tamaño JSON: {size_kb:.1f} KB")
    print(f"Tokens estimados: ~{estimated_tokens}")

    if estimated_tokens > 4000 or project_map["total_files"] > 150:
        print("\n⚠️  [ADVERTENCIA DE TOKENS]")
        print(
            f"   El proyecto es grande para un mapa JSON sin filtrar (~{estimated_tokens} tokens, {project_map['total_files']} archivos)."
        )
        print("   Inyectar este JSON en el contexto de un LLM puede ser ineficiente.")
        print("   Recomendaciones:")
        print("     1. Para búsqueda con 'rag-json', conservar este mapa completo (sin '--light') para máximo contexto.")
        print("     2. Para lectura directa en prompt, usar '--light' o '--exclude \"patron/**\"'.")


if __name__ == "__main__":
    main()
