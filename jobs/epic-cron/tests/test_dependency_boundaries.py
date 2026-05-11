"""Dependency boundary checks for epic-cron."""

import ast
from pathlib import Path


FORBIDDEN_IMPORTS = {
    "submit_api",
    "submit_cron",
    "compliance_api",
    "condition_api",
}


def _python_files():
    project_root = Path(__file__).resolve().parents[1]
    for folder_name in ("src", "tasks"):
        yield from (project_root / folder_name).rglob("*.py")
    yield project_root / "invoke_jobs.py"


def test_cron_does_not_import_sibling_application_packages():
    """epic-cron should not import app internals from Submit, Compliance, or Condition."""
    violations = []

    for path in _python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    package_name = alias.name.split(".")[0]
                    if package_name in FORBIDDEN_IMPORTS:
                        violations.append(f"{path}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                package_name = node.module.split(".")[0]
                if package_name in FORBIDDEN_IMPORTS:
                    violations.append(f"{path}: imports from {node.module}")

    assert violations == []
