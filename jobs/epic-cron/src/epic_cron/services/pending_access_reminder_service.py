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
"""Service to send pending access request reminder emails."""
import logging
from typing import List

from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError

from epic_cron.repositories.access_request_repository import (
    AccessRequestRepository,
    PendingAccessRequest,
)
from epic_cron.services.centre_email_service import CentreEmailService
from epic_cron.services.keycloak_service import KeycloakService

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "pending_access_reminder.html"


REQUEST_ACCESS_PATH = "/request-access"


def _build_user_links(
    requests: List[PendingAccessRequest], base_url: str
) -> List[dict]:
    """
    Build list of {name, url} for template.
    Fetches user name and @idir id from Keycloak when KEYCLOAK_EMAILER_* is configured.
    """
    base_url = (base_url or "").rstrip("/")
    request_access_base = f"{base_url}{REQUEST_ACCESS_PATH}" if base_url else ""
    result = []
    for r in requests:
        display_name = r.name
        try:
            user = KeycloakService.get_user_by_guid(r.user_id)
            if user:
                display_name = KeycloakService.format_user_display_name(
                    user, r.user_id, include_username=False
                )
        except Exception:  # pylint: disable=broad-except
            pass
        result.append(
            {
                "name": display_name,
                "url": f"{request_access_base}/auth/users/{r.user_id}" if request_access_base else "",
            }
        )
    return result


def run_pending_access_reminder(repository: AccessRequestRepository) -> bool:
    """
    Find pending access requests older than configured hours, send one reminder email.

    Returns True if an email was sent, False if no pending requests or config missing.
    """
    hours = current_app.config.get("PENDING_ACCESS_REMINDER_HOURS", 48)
    recipient = (current_app.config.get("PENDING_ACCESS_REMINDER_EMAIL") or "").strip()
    base_url = (current_app.config.get("REQUEST_ACCESS_BASE_URL") or "").strip()
    sender = current_app.config.get("SENDER_EMAIL") or ""

    if not recipient:
        logger.warning(
            "PENDING_ACCESS_REMINDER_EMAIL is not set; skipping pending access reminder."
        )
        return False
    if not sender:
        raise BadRequestError("SENDER_EMAIL is not configured")

    pending = repository.find_pending_older_than_hours(hours)
    if not pending:
        logger.info("No pending access requests older than %s hours.", hours)
        return False

    base_url = base_url.rstrip("/")
    request_access_base = f"{base_url}{REQUEST_ACCESS_PATH}" if base_url else ""
    user_links = _build_user_links(pending, base_url)
    review_all_url = f"{request_access_base}/auth" if request_access_base else ""

    subject = "Reminder: Pending EPIC Access Requests"
    email_details = EmailDetails(
        template_name=TEMPLATE_NAME,
        body_args={
            "users": user_links,
            "review_all_url": review_all_url,
            "hours": hours,
        },
        subject=subject,
        sender=sender,
        recipients=[recipient],
    )

    CentreEmailService.send_email(email_details)
    logger.info(
        "Sent pending access reminder to %s for %d request(s).",
        recipient,
        len(pending),
    )
    return True
