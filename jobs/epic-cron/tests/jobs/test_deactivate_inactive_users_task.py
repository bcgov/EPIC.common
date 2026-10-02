"""Tests for the DeactivateInactiveUsers task wrapper."""

import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
for _path in (PROJECT_ROOT, SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from tasks.deactivate_inactive_users import DeactivateInactiveUsers  # noqa: E402


def test_task_delegates_to_service():
    """The task builds a submit session and calls the service exactly once."""
    app = Flask(__name__)
    with app.app_context(), patch(
        "tasks.deactivate_inactive_users.init_submit_session"
    ) as init_session, patch(
        "tasks.deactivate_inactive_users.InactiveUserService"
    ) as service:
        session_factory = object()
        init_session.return_value = session_factory

        DeactivateInactiveUsers.deactivate_inactive_users()

        init_session.assert_called_once()
        service.deactivate_inactive_proponents.assert_called_once_with(session_factory)
