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
"""MET Publish Scheduled Engagements."""
from datetime import datetime

from flask import current_app

from epic_cron.models.db import init_submit_db, ma
from epic_cron.services.mail_service import EmailService


class SubmitMailer:  # pylint:disable=too-few-public-methods
    """Task to publish scheduled Engagements due."""

    @classmethod
    def send_mail(cls):
        """Publish the scheduled engagements."""
        init_submit_db(current_app)
        ma.init_app(current_app)
        current_app.logger.info('Starting Email At---{}'.format(datetime.now()))
        EmailService.process_email_queue()
