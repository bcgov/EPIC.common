from functools import partial
from typing import List

from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.models import db
from epic_cron.repositories.submit_repository import SubmitEmailQueueEntry, SubmitRepository
from epic_cron.services.ches_service import ChesApiService
from epic_cron.services.invitation_email_service import InvitationEmailService
from epic_cron.services.package_submission_email_service import PackageSubmissionEmailService
from epic_cron.services.request_update_email_service import RequestUpdateEmailService
from epic_cron.services.resubmission_email_service import ResubmissionEmailService
from epic_cron.services.template_renderer import TemplateRenderer
from epic_cron.utils import constants


class EmailService:  # pylint: disable=too-few-public-methods
    """Handles Submit email queue processing."""

    @staticmethod
    def process_email_queue():
        """Process all pending emails in the Submit email queue."""
        repository = SubmitRepository(db.session)
        pending_emails = EmailService.find_pending(repository=repository)
        if not pending_emails:
            current_app.logger.info("No pending emails found.")
            return

        current_app.logger.info(f"Number of pending emails: {len(pending_emails)}")
        for email_entry in pending_emails:
            try:
                email_processor = EmailService._get_email_processor(email_entry)
                email_processor(repository, email_entry)
            except Exception as e:
                current_app.logger.error(
                    "Error processing Submit email %s: %s",
                    email_entry.id,
                    e,
                    exc_info=True,
                )
                repository.rollback()
                repository.mark_email_failed(email_entry.id, str(e))

    @classmethod
    def _get_email_processor(cls, email_entry: SubmitEmailQueueEntry) -> callable:
        """Get the email processor based on the template name."""
        email_processors = {
            constants.MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE: cls._process_package_submission_email,
            constants.MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE: cls._process_request_update_creation_email,
            constants.MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE: cls._process_resubmission_request_email,
            constants.MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE: partial(
                cls._process_package_submission_email,
                template_name=constants.MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE,
            ),
            constants.NEW_USER_INVITATION_EMAIL_TEMPLATE: cls._process_new_user_invitation_email,
            constants.SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE: cls._process_awaiting_manager_approval_email,
        }
        template = email_entry.template_name
        if template not in email_processors:
            raise BadRequestError(f"Unsupported email template: {template}")
        return email_processors.get(template)

    @staticmethod
    def _process_awaiting_manager_approval_email(
        repository: SubmitRepository,
        email_entry: SubmitEmailQueueEntry,
    ):
        """Process email notifying MPT Managers that a package awaits Manager's approval."""
        from epic_cron.services.keycloak_service import KeycloakService

        package = repository.get_awaiting_manager_email_data(email_entry.entity_id)
        if not package:
            raise BadRequestError(f"Package with ID {email_entry.entity_id} not found.")

        manager_emails = KeycloakService.get_eao_manager_emails()
        if not manager_emails:
            raise BadRequestError(
                "No EAO_MANAGER group members with email found (check Keycloak admin config)"
            )

        email_details = PackageSubmissionEmailService.prepare_awaiting_manager_approval_email(
            package,
            manager_emails,
        )
        EmailService.send_email(email_details)
        repository.mark_email_sent(email_entry.id)

    @staticmethod
    def _process_package_submission_email(
        repository: SubmitRepository,
        email_entry: SubmitEmailQueueEntry,
        template_name=None,
    ):
        """Process email entry for package submission."""
        package = repository.get_package_email_data(email_entry.entity_id)
        if not package:
            raise BadRequestError(f"Package with ID {email_entry.entity_id} not found.")

        email_details = PackageSubmissionEmailService.prepare_package_submission_email_confirmation(
            package,
            template_name,
        )
        EmailService.send_email(email_details)
        repository.mark_email_sent(email_entry.id)

    @staticmethod
    def _process_request_update_creation_email(
        repository: SubmitRepository,
        email_entry: SubmitEmailQueueEntry,
    ):
        """Process email entry for request update creation."""
        package = repository.get_package_email_data(email_entry.entity_id)
        if not package:
            raise BadRequestError(f"Package with ID {email_entry.entity_id} not found.")

        email_details = RequestUpdateEmailService.prepare_update_request_creation_email_notification(package)
        EmailService.send_email(email_details)
        repository.mark_email_sent(email_entry.id)

    @staticmethod
    def _process_resubmission_request_email(
        repository: SubmitRepository,
        email_entry: SubmitEmailQueueEntry,
    ):
        """Process email entry for resubmission invitation."""
        package = repository.get_package_email_data(email_entry.entity_id)
        if not package:
            raise BadRequestError(f"Package with ID {email_entry.entity_id} not found.")

        project_admin_emails = repository.get_project_admin_emails(package.account_project_id)
        email_details = ResubmissionEmailService.prepare_resubmission_request_email(
            package,
            project_admin_emails,
        )
        EmailService.send_email(email_details)
        repository.mark_email_sent(email_entry.id)

    @staticmethod
    def _process_new_user_invitation_email(
        repository: SubmitRepository,
        email_entry: SubmitEmailQueueEntry,
    ):
        """Process email entry for new user invitation."""
        invitation = repository.get_invitation_email_data(email_entry.entity_id)
        if not invitation:
            raise BadRequestError(f"Invitation with ID {email_entry.entity_id} not found.")

        email_details = InvitationEmailService.prepare_invitation_email_notification(invitation)
        EmailService.send_email(email_details)
        repository.mark_email_sent(email_entry.id)

    @staticmethod
    def send_email(email_details: EmailDetails):
        """Send email using the CHES API."""
        try:
            payload = TemplateRenderer.compose_email(
                email_details=email_details,
                domain='submit',
                web_url=current_app.config.get("WEB_URL", ""),
                environment=current_app.config.get("ENVIRONMENT", ""),
            )
            email_api_service = ChesApiService()
            return email_api_service.send_email(payload)
        except Exception as e:
            raise BadRequestError(f"Failed to send email: {str(e)}")

    @staticmethod
    def find_pending(
        limit=100,
        repository: SubmitRepository | None = None,
    ) -> List[SubmitEmailQueueEntry]:
        """Find pending Submit emails, with a limit for performance."""
        repository = repository or SubmitRepository(db.session)
        return repository.find_pending_emails(limit=limit)
