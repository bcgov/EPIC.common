"""Dependency boundary checks for epic-cron."""

import ast
from pathlib import Path


FORBIDDEN_IMPORTS = {
    "compliance_api",
    "condition_api",
}

SUBMIT_SYNC_FILES = [
    "invoke_jobs.py",
    "tasks/phase_extractor.py",
    "tasks/project_extractor.py",
    "tasks/proponent_extractor.py",
    "tasks/proponent_status_updater.py",
    "tasks/sync_approved_condition.py",
    "tasks/work_extractor.py",
    "src/epic_cron/services/approved_condition_service.py",
    "src/epic_cron/services/approved_condition_sync_service.py",
]


def _python_files():
    project_root = Path(__file__).resolve().parents[1]
    for folder_name in ("src", "tasks"):
        yield from (project_root / folder_name).rglob("*.py")
    yield project_root / "invoke_jobs.py"


def _find_forbidden_imports(path, forbidden_imports):
    violations = []
    tree = ast.parse(path.read_text(), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                package_name = alias.name.split(".")[0]
                if package_name in forbidden_imports:
                    violations.append(f"{path}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            package_name = node.module.split(".")[0]
            if package_name in forbidden_imports:
                violations.append(f"{path}: imports from {node.module}")

    return violations


def test_cron_does_not_import_compliance_or_condition_packages():
    """epic-cron should not import Compliance or Condition application packages."""
    violations = []

    for path in _python_files():
        violations.extend(_find_forbidden_imports(path, FORBIDDEN_IMPORTS))

    assert violations == []


def test_submit_sync_paths_do_not_import_submit_packages():
    """Submit sync code should use local models instead of submit_api or submit_cron."""
    project_root = Path(__file__).resolve().parents[1]
    violations = []

    for relative_path in SUBMIT_SYNC_FILES:
        path = project_root / relative_path
        violations.extend(_find_forbidden_imports(path, {"submit_api", "submit_cron"}))

    assert violations == []
