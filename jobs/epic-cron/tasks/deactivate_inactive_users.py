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
"""Task: deactivate proponent users inactive for 6+ months."""
from datetime import datetime

from flask import current_app

from epic_cron.models.db import init_submit_session
from epic_cron.services.inactive_user_service import InactiveUserService


class DeactivateInactiveUsers:  # pylint:disable=too-few-public-methods
    """Task to deactivate proponent users with prolonged inactivity."""

    @classmethod
    def deactivate_inactive_users(cls):
        """Deactivate proponents whose last login is older than the threshold."""
        current_app.logger.info(
            'Starting Deactivate Inactive Users---%s', datetime.now()
        )
        session_factory = init_submit_session(current_app)
        InactiveUserService.deactivate_inactive_proponents(session_factory)
