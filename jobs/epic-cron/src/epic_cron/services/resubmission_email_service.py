from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.data_classes.submit_email import PackageEmailData
from epic_cron.utils import submit_constants


class ResubmissionEmailService:
    """Build email notifications for Submit resubmission requests."""

    @classmethod
    def prepare_resubmission_request_email(
        cls,
        package: PackageEmailData,
        project_admin_emails: list[str],
    ) -> EmailDetails:
        """Prepare email details for resubmission request for project admins."""
        if not project_admin_emails:
            raise BadRequestError("No admin users found for this account project")

        web_url = current_app.config.get('WEB_URL')
        submission_link = (
            f"{web_url}/proponent/projects/{package.account_project_id}"
            f"/submission-packages/{package.package_id}"
        )
        return EmailDetails(
            template_name=submit_constants.MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE,
            body_args={
                'submission_link': submission_link,
                'package_name': package.package_name,
            },
            subject=f'Invitation to resubmit a new version of {package.package_name} in EPIC.submit',
            sender=current_app.config.get('SENDER_EMAIL'),
            recipients=project_admin_emails,
        )
