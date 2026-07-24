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

from epic_cron.models.db import init_submit_session, ma, session_scope
from epic_cron.processors.submit import PROCESSORS
from epic_cron.repositories.email_repository import EmailRepository
from epic_cron.services.mail_service import EmailService


class SubmitMailer:  # pylint:disable=too-few-public-methods
    """Task to publish scheduled Engagements due."""

    @classmethod
    def send_mail(cls):
        """Send queued Submit emails using payload processors."""
        session_factory = init_submit_session(current_app)
        ma.init_app(current_app)
        current_app.logger.info('Starting Email At---{}'.format(datetime.now()))

        with session_scope(session_factory) as session:
            for template_name, processor in PROCESSORS.items():
                current_app.logger.debug(f'Registering processor for template: {template_name}')
                EmailService.register_processor(template_name, processor)

            repo = EmailRepository(session)
            EmailService.process_email_queue(repo, limit=100)
