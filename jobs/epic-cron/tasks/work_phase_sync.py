# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Archive previous-phase packages and create new-phase mandatory packages in Submit."""
from datetime import datetime

from flask import current_app

from epic_cron.models.db import init_submit_session
from epic_cron.services.work_phase_sync_service import WorkPhaseSyncService


class WorkPhaseSync:  # pylint:disable=too-few-public-methods
    """Task to reconcile each work's Submit packages with the work's current phase."""

    @classmethod
    def run(cls):
        """Trigger the Submit phase reconcile for every work with an onboarded account project."""
        current_app.logger.info('Starting Work Phase Sync---{}'.format(datetime.now()))
        submit_session = init_submit_session(current_app)
        return WorkPhaseSyncService.sync_work_phases(submit_session)

    @classmethod
    def extract_then_sync(cls, extract):
        """Run the work extraction, then the phase sync, even when the extraction failed.

        The phase sync works from what is already stored in Submit, so it can still finish work left over
        from an earlier run when the Track fetch or the upsert fails. Every stage is attempted, and the
        first error is raised afterwards so the job exits non-zero.
        """
        errors = []
        for stage in (extract, cls.run):
            try:
                stage()
            except Exception as err:  # pylint:disable=broad-except  # noqa: B902 - collected and re-raised below
                current_app.logger.error('Work sync stage %s failed: %s', getattr(stage, '__name__', stage), err)
                errors.append(err)
        if errors:
            raise errors[0]
