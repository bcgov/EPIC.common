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
"""Update projects with approved condition from condition repository."""
from datetime import datetime

from flask import current_app

from epic_cron.models.db import init_submit_db, init_submit_session, ma
from epic_cron.services.approved_condition_sync_service import ApprovedConditionService


class SyncApprovedCondition:  # pylint:disable=too-few-public-methods
    """Task to update projects having approved condition."""

    @classmethod
    def sync_approved_condition(cls):
        """Update projects having approved condition."""
        init_submit_db(current_app)
        submit_session = init_submit_session(current_app)
        ma.init_app(current_app)
        current_app.logger.info('Starting Approved Condition Sync---{}'.format(datetime.now()))
        ApprovedConditionService.sync_projects_with_approved_conditions(submit_session)
