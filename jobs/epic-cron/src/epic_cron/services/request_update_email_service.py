from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.repositories.submit_repository import PackageEmailData
from epic_cron.utils import constants


class RequestUpdateEmailService:  # pylint: disable=too-few-public-methods
    """Build email notifications for Submit update requests."""

    @classmethod
    def prepare_update_request_creation_email_notification(cls, package: PackageEmailData) -> EmailDetails:
        """Prepare email details for update request creation."""
        if not package.submitter_name or not package.submitter_email:
            raise BadRequestError(f"Submitter for package {package.package_id} not found")

        sender_email = cls.get_email_sender_for_package_type(package.package_type)
        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.package_type}")

        sender_name = cls.get_sender_name_for_package_type(package.package_type)
        if not sender_name:
            raise BadRequestError(f"Sender name not found for package type: {package.package_type}")

        return EmailDetails(
            template_name=constants.MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE,
            body_args={
                'epic_submit_link': current_app.config.get('WEB_URL'),
                'submitter_name': package.submitter_name,
                'package_name': package.package_name,
                'sender_name': sender_name,
            },
            subject='Action Required: Update Your Submission',
            sender=sender_email,
            recipients=[package.submitter_email],
        )

    @staticmethod
    def get_email_sender_for_package_type(package_type: str) -> str:
        """Get the email sender for the package type."""
        return constants.SUBMISSION_PACKAGE_TYPE_EMAIL_SENDER_MAP.get(package_type, None)

    @staticmethod
    def get_sender_name_for_package_type(package_type: str) -> str:
        """Get the sender name for the package type."""
        return constants.SUBMISSION_PACKAGE_TYPE_SENDER_MAP.get(package_type, None)
