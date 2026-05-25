"""Tests for Submit schema version selection."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasks.project_extractor import ProjectExtractor, TargetSystem


class ProjectRow:
    """Simple row stand-in with SQLAlchemy row mapping shape."""

    def __init__(self, data):
        self._mapping = data


def test_submit_project_values_include_proponent_name_for_v1():
    """Submit v1 writes proponent_name to projects."""
    project = ProjectRow({
        "id": 1,
        "name": "Example Project",
        "epic_guid": "abc",
        "proponent_id": 2,
        "proponent_name": "Example Holder",
        "ea_certificate": "EAC-1",
    })

    target_model = MagicMock()

    app = Flask(__name__)
    with app.app_context(), patch("tasks.project_extractor.session_scope") as session_scope:
        session = session_scope.return_value.__enter__.return_value
        session.query.return_value.filter_by.return_value.first.return_value = None

        ProjectExtractor._upsert_into_target_db([project], object(), target_model, TargetSystem.SUBMIT)

    target_model.assert_called_once_with(
        id=1,
        name="Example Project",
        epic_guid="abc",
        proponent_id=2,
        ea_certificate="EAC-1",
        proponent_name="Example Holder",
    )


def test_submit_project_values_do_not_include_proponent_name_for_v2():
    """Submit v2 does not write proponent_name to projects."""
    project = ProjectRow({
        "id": 1,
        "name": "Example Project",
        "epic_guid": "abc",
        "proponent_id": 2,
        "proponent_name": "Example Holder",
        "ea_certificate": "EAC-1",
    })

    target_model = MagicMock()

    app = Flask(__name__)
    with app.app_context(), patch("tasks.project_extractor.session_scope") as session_scope:
        session = session_scope.return_value.__enter__.return_value
        session.query.return_value.filter_by.return_value.first.return_value = None

        ProjectExtractor._upsert_into_target_db(
            [project],
            object(),
            target_model,
            TargetSystem.SUBMIT,
            submit_schema_version="v2",
        )

    call_kwargs = target_model.call_args.kwargs
    assert call_kwargs == {
        "id": 1,
        "name": "Example Project",
        "epic_guid": "abc",
        "proponent_id": 2,
        "ea_certificate": "EAC-1",
    }
    assert "proponent_name" not in call_kwargs


def test_submit_cron_shell_defaults_to_v1():
    """The shell wrapper defaults to v1 but passes through an explicit argument."""
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "run_project_cron_submit.sh").read_text()

    assert 'SUBMIT_SCHEMA_VERSION="${1:-v1}"' in script
    assert 'python3 invoke_jobs.py SUBMIT "${SUBMIT_SCHEMA_VERSION}"' in script
