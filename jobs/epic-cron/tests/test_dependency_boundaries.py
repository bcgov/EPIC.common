"""Dependency boundary checks for epic-cron."""

import ast
from pathlib import Path


SIBLING_APPLICATION_IMPORTS = {
    "submit_api",
    "submit_cron",
    "compliance_api",
    "condition_api",
}

MAILER_ALLOWED_FILES = {
    Path("src/epic_cron/services/centre_email_service.py"),
    Path("src/epic_cron/services/invitation_email_service.py"),
    Path("src/epic_cron/services/mail_service.py"),
    Path("src/epic_cron/services/package_submission_email_service.py"),
    Path("src/epic_cron/services/pending_access_reminder_service.py"),
    Path("src/epic_cron/services/request_update_email_service.py"),
    Path("src/epic_cron/services/resubmission_email_service.py"),
    Path("tasks/pending_access_reminder.py"),
}


def _python_files():
    project_root = Path(__file__).resolve().parents[1]
    for folder_name in ("src", "tasks"):
        yield from (project_root / folder_name).rglob("*.py")
    yield project_root / "invoke_jobs.py"


def test_cron_does_not_import_sibling_application_packages():
    """Sync code should not import app internals from sibling applications."""
    violations = []
    project_root = Path(__file__).resolve().parents[1]

    for path in _python_files():
        relative_path = path.relative_to(project_root)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    package_name = alias.name.split(".")[0]
                    if (
                        package_name in SIBLING_APPLICATION_IMPORTS
                        and relative_path not in MAILER_ALLOWED_FILES
                    ):
                        violations.append(f"{path}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                package_name = node.module.split(".")[0]
                if (
                    package_name in SIBLING_APPLICATION_IMPORTS
                    and relative_path not in MAILER_ALLOWED_FILES
                ):
                    violations.append(f"{path}: imports from {node.module}")

    assert violations == []
