#!/usr/bin/env python3
"""Regression checks for context selection and compression."""

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_map() -> dict:
    return {
        "project_name": "demo",
        "total_symbols": 5,
        "architecture": {"entry_points": ["src/main.ts"], "core_modules": ["src"]},
        "files": [
            {"path": "src/main.ts", "summary": "Punto de entrada", "imports": ["@/auth"],
             "exports": ["start"], "functions": [{"name": "start"}], "classes": [], "complexity": "high"},
            {"path": "src/auth.ts", "summary": "Autenticación OAuth", "imports": [],
             "exports": ["login"], "functions": [{"name": "login"}], "classes": [], "complexity": "medium"},
            {"path": "src/other.ts", "summary": "Utilidad", "imports": [],
             "exports": [], "functions": [], "classes": [], "complexity": "low"},
        ],
        "dependency_graph": {
            "src/main.ts": ["src/auth.ts"], "src/auth.ts": [], "src/other.ts": []
        },
    }


def test_injector_and_compressor() -> None:
    injector_module = load_script("inject_relevant")
    compressor_module = load_script("compress_context")
    with tempfile.TemporaryDirectory() as directory:
        map_path = Path(directory) / "map.json"
        map_path.write_text(json.dumps(sample_map()), encoding="utf-8")

        context = injector_module.RelevantContextInjector(map_path).build_context(
            "autenticación OAuth", light=True, include_dependents=True
        )
        assert {item["path"] for item in context["files"]} == {"src/auth.ts", "src/main.ts"}
        assert "functions" not in context["files"][0]
        assert context["estimated_tokens"] > 0

        compressed = compressor_module.ContextCompressor().compress_map(map_path, ratio=0.5)
        assert compressed["dependency_graph"]["src/main.ts"] == ["src/auth.ts"]
        assert compressed["metadata"]["compression"]["method"] == "deterministic"


if __name__ == "__main__":
    test_injector_and_compressor()
    print("context tools smoke test: ok")