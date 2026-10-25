#!/usr/bin/env python3
"""Fast regression checks for the compact project map generator."""

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_map.py"
SPEC = importlib.util.spec_from_file_location("generate_map", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_real_symbols_and_compact_defaults() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "src").mkdir()
        (root / "src" / "utils.ts").write_text("export function helper() { return 1; }\n", encoding="utf-8")
        (root / "src" / "main.ts").write_text(
            "import { helper } from '@/utils';\n"
            "const acc = { linkedAccount: true };\n"
            "const catMap = new Map();\n"
            "const DEFAULT_DOLLAR_TYPE = 'USD';\n"
            "const arrow = (value) => value;\n"
            "function declared() { return helper(); }\n",
            encoding="utf-8",
        )
        (root / "src" / "models.py").write_text(
            "linked_account = {}\n\n"
            "async def fetch_data(value):\n    return value\n",
            encoding="utf-8",
        )
        (root / "pnpm-lock.yaml").write_text("should be ignored\n", encoding="utf-8")

        project_map = MODULE.ProjectMapper(root).generate_map()
        functions = {
            symbol["name"]
            for item in project_map["files"]
            for symbol in item.get("functions", [])
        }
        assert functions == {"arrow", "declared", "fetch_data", "helper"}
        assert project_map["total_symbols"] == 4
        assert project_map["dependency_graph"]["src/main.ts"] == ["src/utils.ts"]
        assert "pnpm-lock.yaml" not in {item["path"] for item in project_map["files"]}
        assert all("line" not in symbol for item in project_map["files"] for symbol in item.get("functions", []))
        with_lines = MODULE.ProjectMapper(root, include_lines=True).generate_map()
        assert all("line" in symbol for item in with_lines["files"] for symbol in item.get("functions", []))

        light = MODULE.ProjectMapper(root, light=True).generate_map()
        assert set(light["files"][0]) == {"path", "summary", "imports", "exports", "complexity"}
        json.dumps(light)


if __name__ == "__main__":
    test_real_symbols_and_compact_defaults()
    print("project mapper smoke test: ok")