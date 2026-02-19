from datetime import datetime
from functools import partial
from typing import List

from flask import current_app
from submit_api.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError
from submit_api.models.email_queue import EmailQueue, EmailStatus
from submit_api.models.invitations import Invitations as InvitationsModel
from submit_api.models.package import Package as PackageModel
from submit_api.utils.constants import (
    MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE, MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE,
    MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE, MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE,
    NEW_USER_INVITATION_EMAIL_TEMPLATE, SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE)

from epic_cron.models import db
from epic_cron.services.ches_service import ChesApiService
from epic_cron.services.invitation_email_service import InvitationEmailService
from epic_cron.services.package_submission_email_service import PackageSubmissionEmailService
from epic_cron.services.request_update_email_service import RequestUpdateEmailService
from epic_cron.services.resubmission_email_service import ResubmissionEmailService


class EmailService:  # pylint: disable=too-few-public-methods
    """Handles the general email sending operations."""

    @staticmethod
    def process_email_queue():
        """Process all pending emails in the email queue."""
        pending_emails = EmailService.find_pending()
        if not pending_emails:
            current_app.logger.info("No pending emails found.")
            return
        current_app.logger.info(f"Number of pending emails: {len(pending_emails)}")
        for email_entry in pending_emails:
            try:
                email_processor = EmailService._get_email_processor(email_entry)
                email_processor(email_entry)
            except Exception as e:
                # Log the error and update the status to FAILED
                email_entry.status = EmailStatus.FAILED.value
                email_entry.error_message = str(e)
                db.session.commit()

    @classmethod
    def _get_email_processor(cls, email_entry: EmailQueue) -> callable:
        """Get the email processor based on the template name."""
        email_processors = {
            MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE: cls._process_package_submission_email,
            MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE: cls._process_request_update_creation_email,
            MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE: cls._process_resubmission_request_email,
            # staff email uses the same content, but just a different template..so reusing the same method passing template name
            MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE: partial(cls._process_package_submission_email, template_name=MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE),
            NEW_USER_INVITATION_EMAIL_TEMPLATE: cls._process_new_user_invitation_email,
            SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE: cls._process_awaiting_manager_approval_email
        }
        template = email_entry.template_name
        if template not in email_processors:
            raise BadRequestError(f"Unsupported email template: {template}")
        return email_processors.get(template)

    @staticmethod
    def _process_awaiting_manager_approval_email(email_entry: EmailQueue):
        """Process email notifying MPT Managers that a package awaits Manager's approval."""
        from epic_cron.services.keycloak_service import KeycloakService
        package_id = email_entry.entity_id
        package: PackageModel = db.session.get(PackageModel, package_id)
        if not package:
            raise BadRequestError(f"Package with ID {package_id} not found.")
        manager_emails = KeycloakService.get_eao_manager_emails()
        if not manager_emails:
            raise BadRequestError(
                "No EAO_MANAGER group members with email found (check Keycloak admin config)"
            )
        email_details = PackageSubmissionEmailService.prepare_awaiting_manager_approval_email(
            package, manager_emails
        )
        EmailService.send_email(email_details)
        email_entry.status = EmailStatus.SENT.value
        email_entry.sent_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def _process_package_submission_email(email_entry: EmailQueue, template_name=None ):
        """Process email entry for package submission."""
        package_id = email_entry.entity_id
        package: PackageModel = db.session.get(PackageModel, package_id)
        if not package:
            raise BadRequestError(f"Package with ID {package_id} not found.")

        email_details = PackageSubmissionEmailService.prepare_package_submission_email_confirmation(package, template_name)

        # Send the email using ChesApiService
        EmailService.send_email(email_details)

        # Update the email queue status to SENT
        email_entry.status = EmailStatus.SENT.value
        email_entry.sent_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def _process_request_update_creation_email(email_entry: EmailQueue):
        """Process email entry for request update creation."""
        package_id = email_entry.entity_id
        package: PackageModel = db.session.get(PackageModel, package_id)
        if not package:
            raise BadRequestError(f"Package with ID {package_id} not found.")

        email_details = RequestUpdateEmailService.prepare_update_request_creation_email_notification(package)

        # Send the email using ChesApiService
        EmailService.send_email(email_details)

        # Update the email queue status to SENT
        email_entry.status = EmailStatus.SENT.value
        email_entry.sent_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def _process_resubmission_request_email(email_entry: EmailQueue):
        """Process email entry for resubmission invitation."""
        package_id = email_entry.entity_id
        package: PackageModel = db.session.get(PackageModel, package_id)
        if not package:
            raise BadRequestError(f"Package with ID {package_id} not found.")

        # Get all PROJECT_ADMIN users for this account project
        project_admin_users = ResubmissionEmailService.get_project_admin_users(package)
        
        # Send email to all project admins
        email_details = ResubmissionEmailService.prepare_resubmission_request_email(
            package, project_admin_users
        )
        EmailService.send_email(email_details)
        
        # Update the original email queue status to SENT
        email_entry.status = EmailStatus.SENT.value
        email_entry.sent_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def _process_new_user_invitation_email(email_entry: EmailQueue):
        """Process email entry for new user invitation."""
        invitation_id = email_entry.entity_id
        invitation: InvitationsModel = db.session.get(InvitationsModel, invitation_id)
        if not invitation:
            raise BadRequestError(f"Invitation with ID {invitation_id} not found.")

        email_details = InvitationEmailService.prepare_invitation_email_notification(invitation)

        # Send the email using ChesApiService
        EmailService.send_email(email_details)

        # Update the email queue status to SENT
        email_entry.status = EmailStatus.SENT.value
        email_entry.sent_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def send_email(email_details: EmailDetails):
        """Send email using the ChesApiService."""
        try:
            email_api_service = ChesApiService()
            return email_api_service.send_email(email_details)
        except Exception as e:
            raise BadRequestError(f"Failed to send email: {str(e)}")

    @staticmethod
    def find_pending(limit=100) -> List[EmailQueue]:
        """Find all pending emails in the queue, with a limit for performance.

        Args:
            limit (int): Maximum number of pending emails to return.

        Returns:
            list[EmailQueue]: List of pending email queue entries.
        """
        return db.session.query(EmailQueue).filter(EmailQueue.status == EmailStatus.PENDING.value).limit(limit).all()
