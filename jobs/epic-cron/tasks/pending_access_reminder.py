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
"""Task: send reminder email for access requests pending longer than configured hours."""
from datetime import datetime

from flask import current_app

from submit_cron.models.db import init_centre_db
from submit_cron.repositories.access_request_repository import AccessRequestRepository
from submit_cron.services.pending_access_reminder_service import run_pending_access_reminder


class PendingAccessReminder:
    """Send reminder email for pending access requests (Centre)."""

    @classmethod
    def run(cls):
        """Query Centre DB for pending access requests and send one reminder email."""
        print("Starting Pending Access Reminder At ", datetime.now())
        session_factory = init_centre_db(current_app)
        session = session_factory()
        try:
            repo = AccessRequestRepository(session)
            run_pending_access_reminder(repo)
        finally:
            session.close()
        print("Completed Pending Access Reminder At ", datetime.now())