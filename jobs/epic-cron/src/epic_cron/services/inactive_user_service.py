# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to deactivate proponent users inactive for a prolonged period.

Business rules:
    - Only proponent users (``users.type == PROPONENT``) are considered.
    - Only users currently ACTIVE are eligible; ACCESS_REVOKED and already
      INACTIVE users are left untouched.
    - A user is deactivated when their ``account_users.last_login_at`` is a real
      timestamp older than the inactivity threshold (6 months). Users with a
      NULL ``last_login_at`` are skipped entirely.
    - No reactivation happens here; this job only moves ACTIVE -> INACTIVE.
"""
import calendar
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import and_

from epic_cron.models.db import session_scope
from epic_cron.models.external.submit import (
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
    USER_TYPE_PROPONENT,
    SubmitAccountUser,
    SubmitUser,
)

# Number of months of inactivity after which a proponent is deactivated.
INACTIVITY_THRESHOLD_MONTHS = 6


def _utc_now():
    """Return the current time as a naive UTC datetime.

    ``account_users.last_login_at`` is stored without timezone info, so the
    cutoff is computed as a naive UTC value to keep the comparison consistent.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _subtract_months(reference, months):
    """Return ``reference`` shifted back by a whole number of calendar months.

    Clamps the day to the last valid day of the resulting month so that dates
    such as the 31st do not overflow into the following month.
    """
    month_index = reference.month - 1 - months
    year = reference.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp to the last valid day of the target month (handles February/leap years).
    last_day = calendar.monthrange(year, month)[1]
    day = min(reference.day, last_day)
    return reference.replace(year=year, month=month, day=day)


class InactiveUserService:
    """Deactivate proponent users who have not logged in for 6+ months."""

    @classmethod
    def deactivate_inactive_proponents(cls, session_factory, reference_time=None):
        """Set stale ACTIVE proponents to INACTIVE and return the count updated.

        :param session_factory: A SQLAlchemy sessionmaker for the Submit DB.
        :param reference_time: Optional naive UTC datetime used as "now"; when
            omitted the current UTC time is used. Injectable for testing.
        :returns: The number of users transitioned to INACTIVE.
        """
        reference = reference_time or _utc_now()
        cutoff = _subtract_months(reference, INACTIVITY_THRESHOLD_MONTHS)
        current_app.logger.info(
            "Deactivating proponents with last_login_at before %s", cutoff.isoformat()
        )

        with session_scope(session_factory) as session:
            stale_users = (
                session.query(SubmitUser)
                .join(SubmitAccountUser, SubmitAccountUser.user_id == SubmitUser.id)
                .filter(
                    and_(
                        SubmitUser.type == USER_TYPE_PROPONENT,
                        SubmitUser.status_id == USER_STATUS_ACTIVE,
                        SubmitAccountUser.last_login_at.isnot(None),
                        SubmitAccountUser.last_login_at < cutoff,
                    )
                )
                .all()
            )

            updated_count = 0
            for user in stale_users:
                user.status_id = USER_STATUS_INACTIVE
                updated_count += 1

            session.commit()

        current_app.logger.info(
            "Deactivated %d inactive proponent user(s).", updated_count
        )
        return updated_count
