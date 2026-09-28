"""Tests for proponent inactivity deactivation (DEACTIVATE_INACTIVE_USERS)."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
for _path in (PROJECT_ROOT, SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from epic_cron.models.external.submit import (  # noqa: E402
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
)
from epic_cron.services.inactive_user_service import (  # noqa: E402
    InactiveUserService,
    _subtract_months,
)


class FakeUser:
    """Minimal stand-in for a SubmitUser row."""

    def __init__(self, user_id, status_id=USER_STATUS_ACTIVE):
        self.id = user_id
        self.status_id = status_id


def _service_with_stale_users(stale_users):
    """Run the service with a mocked session yielding the given stale users.

    Returns a tuple of (updated_count, session_mock).
    """
    app = Flask(__name__)
    with app.app_context(), patch(
        "epic_cron.services.inactive_user_service.session_scope"
    ) as session_scope:
        session = session_scope.return_value.__enter__.return_value
        query = session.query.return_value.join.return_value.filter.return_value
        query.all.return_value = stale_users

        count = InactiveUserService.deactivate_inactive_proponents(
            session_factory=object(),
            reference_time=datetime(2026, 9, 28),
        )
        return count, session


def test_deactivates_stale_active_proponents():
    """Users returned by the stale query are flipped to INACTIVE and counted."""
    users = [FakeUser(1), FakeUser(2)]

    count, session = _service_with_stale_users(users)

    assert count == 2
    assert all(u.status_id == USER_STATUS_INACTIVE for u in users)
    session.commit.assert_called_once()


def test_no_stale_users_returns_zero():
    """When nothing matches the filter, nothing is updated and count is 0."""
    count, session = _service_with_stale_users([])

    assert count == 0
    session.commit.assert_called_once()


def test_cutoff_is_six_months_before_reference():
    """The inactivity cutoff is exactly six calendar months before now."""
    reference = datetime(2026, 9, 28, 3, 30)

    cutoff = _subtract_months(reference, 6)

    assert cutoff == datetime(2026, 3, 28, 3, 30)


def test_cutoff_clamps_day_for_shorter_month():
    """Subtracting months clamps the day to the last valid day of the month."""
    # August 31 minus 6 months lands in February, which has no 31st.
    reference = datetime(2026, 8, 31)

    cutoff = _subtract_months(reference, 6)

    assert cutoff == datetime(2026, 2, 28)


def test_cutoff_crosses_year_boundary():
    """Subtracting months rolls the year back when needed."""
    reference = datetime(2026, 2, 15)

    cutoff = _subtract_months(reference, 6)

    assert cutoff == datetime(2025, 8, 15)
