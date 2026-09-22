"""Core stays free of framework and provider imports."""

import ast
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2] / "agentflow" / "core"
FORBIDDEN_ROOTS = frozenset(
    {
        "fastapi",
        "sqlalchemy",
        "alembic",
        "pydantic",
        "codex",
        "claude",
        "gemini",
        "electron",
        "react",
    }
)


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_core_does_not_import_frameworks_or_providers() -> None:
    offenders: list[str] = []
    for path in sorted(CORE_ROOT.rglob("*.py")):
        found = _imported_roots(path) & FORBIDDEN_ROOTS
        if found:
            offenders.append(f"{path.name}: {', '.join(sorted(found))}")
    assert offenders == []
