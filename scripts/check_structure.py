#!/usr/bin/env python3
"""Check source limits, pipeline imports, and offline page resources."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import sysconfig

try:
    from .js_guard import js_functions
    from .page_guard import page_load_failures
except ImportError:
    from js_guard import js_functions
    from page_guard import page_load_failures


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_LIMIT = 50
SOURCE_LIMIT = 500
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
SOURCE_SUFFIXES = {".py", ".js", ".css"}


def source_files(root: Path) -> list[Path]:
    """List Python, JavaScript, and CSS files outside generated environments."""
    return sorted(path for path in root.rglob("*")
                  if path.is_file() and path.suffix in SOURCE_SUFFIXES
                  and not any(part in SKIP_DIRS for part in path.relative_to(root).parts))


def python_functions(source: str) -> list[tuple[str, int, int]]:
    """Return Python function names, start lines, and physical line spans."""
    tree = ast.parse(source)
    return [(node.name, node.lineno, getattr(node, "end_lineno", node.lineno) - node.lineno + 1)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def local_modules(pipeline: Path) -> set[str]:
    """Accept package imports and the bare imports used by pipeline scripts."""
    modules = {"pipeline"}
    for path in pipeline.rglob("*.py"):
        parts = list(path.relative_to(pipeline).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            dotted = ".".join(parts)
            modules.update({dotted, f"pipeline.{dotted}", parts[-1]})
    return modules


def is_stdlib(module: str) -> bool:
    """Recognize stdlib roots on Python 3.9 as well as newer releases."""
    names = getattr(sys, "stdlib_module_names", None)
    if names is not None:
        return module in names
    if module in sys.builtin_module_names or module == "__future__":
        return True
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError, ModuleNotFoundError):
        return False
    if spec is None:
        return False
    origins = [spec.origin] if spec.origin else []
    origins.extend(spec.submodule_search_locations or [])
    stdlib_paths = [sysconfig.get_path(key) for key in ("stdlib", "platstdlib")]
    roots = [Path(path).resolve() for path in stdlib_paths if path]
    for origin in origins:
        if origin in {"built-in", "frozen"}:
            return True
        candidate = Path(origin).resolve()
        if {"site-packages", "dist-packages"}.intersection(candidate.parts):
            continue
        if any(candidate == root or candidate.is_relative_to(root) for root in roots):
            return True
    return False


def import_failures(path: Path, source: str, own_modules: set[str]) -> list[str]:
    """Reject imports outside the stdlib and this pipeline package."""
    failures = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = list(path.relative_to(ROOT).parent.parts)
                for _ in range(node.level - 1):
                    if parts:
                        parts.pop()
                base = ".".join(parts)
                target = f"{base}.{node.module}" if node.module else base
                local = target in own_modules or all(
                    alias.name == "*" or f"{target}.{alias.name}" in own_modules
                    for alias in node.names
                )
                if not local:
                    failures.append(f"{path.relative_to(ROOT)}:{node.lineno}: unresolved local import {target}")
                continue
            if not node.module:
                continue
            target = node.module
            local = target in own_modules or any(
                alias.name != "*" and f"{target}.{alias.name}" in own_modules
                for alias in node.names
            )
            if local or is_stdlib(target.split(".", 1)[0]):
                continue
            failures.append(f"{path.relative_to(ROOT)}:{node.lineno}: non-stdlib import {target}")
            continue
        else:
            continue
        for module in modules:
            root = module.split(".", 1)[0]
            if module not in own_modules and root not in own_modules and not is_stdlib(root):
                failures.append(f"{path.relative_to(ROOT)}:{node.lineno}: non-stdlib import {module}")
    return failures


def inspect_source(path: Path, own_modules: set[str]) -> list[str]:
    """Apply source line, function line, and pipeline import limits."""
    relative = path.relative_to(ROOT)
    source = path.read_text(encoding="utf-8")
    failures = []
    if len(source.splitlines()) > SOURCE_LIMIT:
        failures.append(f"{relative}: {len(source.splitlines())} lines (limit {SOURCE_LIMIT})")
    if path.suffix == ".py":
        functions = python_functions(source)
        if relative.parts[0] == "pipeline":
            failures.extend(import_failures(path, source, own_modules))
    elif path.suffix == ".js":
        functions = js_functions(source)
    else:
        functions = []
    for name, start, span in functions:
        if span > FUNCTION_LIMIT:
            failures.append(f"{relative}:{start}: {name} is {span} lines (limit {FUNCTION_LIMIT})")
    return failures


def main() -> int:
    pipeline = ROOT / "pipeline"
    modules = local_modules(pipeline)
    failures = []
    for path in source_files(ROOT):
        try:
            failures.extend(inspect_source(path, modules))
        except (SyntaxError, UnicodeError) as error:
            failures.append(f"{path.relative_to(ROOT)}: cannot inspect source ({error})")
    page = ROOT / "pulse.html"
    if page.exists():
        failures.extend(page_load_failures(page, ROOT))
    if failures:
        print("Structure check failed:", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Structure check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
