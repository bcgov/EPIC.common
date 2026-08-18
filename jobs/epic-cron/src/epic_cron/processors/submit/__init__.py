"""Processors for Submit email queue payloads."""
from typing import Callable, Dict

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.models.email_job import EmailJob


MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE = 'management_plan_submission_verification.html'
MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE = 'management_plan_update_request_created.html'
NEW_USER_INVITATION_EMAIL_TEMPLATE = 'new_user_invitation.html'
NEW_USER_INVITATION_ACCOUNT_ADMIN_EMAIL_TEMPLATE = 'new_user_invitation_account_admin.html'
NEW_USER_INVITATION_PROJECT_ADMIN_EMAIL_TEMPLATE = 'new_user_invitation_project_admin.html'
NEW_USER_INVITATION_COLLABORATOR_EMAIL_TEMPLATE = 'new_user_invitation_collaborator.html'
MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE = 'management_plan_submission_notify_staff.html'
SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE = 'submission_awaiting_manager_approval.html'
MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE = 'resubmission_request.html'
SUBMISSION_WITHDRAWN_CONFIRMATION_EMAIL_TEMPLATE = 'submission_withdrawn_confirmation.html'


def process_submit_email(job: EmailJob) -> EmailDetails:
    """Build EmailDetails from a Submit-owned queue payload."""
    payload = job.payload or {}
    missing = [field for field in ('sender', 'recipients', 'subject') if not payload.get(field)]
    if missing:
        raise BadRequestError(f"Missing required payload fields: {', '.join(missing)}")

    recipients = payload['recipients']
    if not isinstance(recipients, list) or not recipients:
        raise BadRequestError("payload.recipients must be a non-empty list")

    body_args = payload.get('body_args') or {}
    if not isinstance(body_args, dict):
        raise BadRequestError("payload.body_args must be an object")

    return EmailDetails(
        template_name=job.template_name,
        body_args=body_args,
        subject=payload['subject'],
        sender=payload['sender'],
        recipients=recipients,
        cc=payload.get('cc') or [],
        bcc=payload.get('bcc') or [],
    )


PROCESSORS: Dict[str, Callable[[EmailJob], EmailDetails]] = {
    MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE: process_submit_email,
    MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE: process_submit_email,
    NEW_USER_INVITATION_EMAIL_TEMPLATE: process_submit_email,
    NEW_USER_INVITATION_ACCOUNT_ADMIN_EMAIL_TEMPLATE: process_submit_email,
    NEW_USER_INVITATION_PROJECT_ADMIN_EMAIL_TEMPLATE: process_submit_email,
    NEW_USER_INVITATION_COLLABORATOR_EMAIL_TEMPLATE: process_submit_email,
    MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE: process_submit_email,
    SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE: process_submit_email,
    MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE: process_submit_email,
    SUBMISSION_WITHDRAWN_CONFIRMATION_EMAIL_TEMPLATE: process_submit_email,
}
