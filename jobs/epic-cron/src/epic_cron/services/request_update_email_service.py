from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError
from submit_api.models.package import Package as PackageModel
from submit_api.utils.constants import MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE

from epic_cron.utils import constants


class RequestUpdateEmailService:  # pylint: disable=too-few-public-methods
    """Handles sending email notifications for package submissions."""

    @classmethod
    def prepare_update_request_creation_email_notification(cls, package: PackageModel) -> EmailDetails:
        """Prepare email details for update request creation."""
        if not package.submitted_by_user or not package.submitted_by_user.account_user:
            raise BadRequestError(f"Submitter with auth_guid {package.submitted_by} not found")
        submitter = package.submitted_by_user.account_user

        sender_email = cls.get_email_sender_for_package_type(package.type.name)
        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.type.name}")

        sender_name = cls.get_sender_name_for_package_type(package.type.name)
        if not sender_name:
            raise BadRequestError(f"Sender name not found for package type: {package.type.name}")

        web_url = current_app.config.get('WEB_URL')
        email_details = EmailDetails(
            template_name=MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE,
            body_args={
                'epic_submit_link': web_url,
                'submitter_name': submitter.full_name,
                'package_name': package.name,
                'sender_name': sender_name,
            },
            subject='Action Required: Update Your Submission',
            sender=sender_email,
            recipients=[submitter.work_email_address],
        )

        return email_details

    @staticmethod
    def get_email_sender_for_package_type(package_type: str) -> str:
        """Get the email sender for the package type."""
        return constants.SUBMISSION_PACKAGE_TYPE_EMAIL_SENDER_MAP.get(package_type, None)

    @staticmethod
    def get_sender_name_for_package_type(package_type: str) -> str:
        """Get the sender name for the package type."""
        return constants.SUBMISSION_PACKAGE_TYPE_SENDER_MAP.get(package_type, None)
