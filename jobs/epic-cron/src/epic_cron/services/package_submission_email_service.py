from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.data_classes.submit_email import PackageEmailData
from epic_cron.utils import submit_constants
from epic_cron.utils.datetime import convert_utc_to_local_str


class PackageSubmissionEmailService:  # pylint: disable=too-few-public-methods
    """Build email notifications for Submit package submissions."""

    @classmethod
    def prepare_package_submission_email_confirmation(
        cls,
        package: PackageEmailData,
        template_name=None,
    ) -> EmailDetails:
        """Prepare email details for a package submission."""
        cls._require_submitter(package)

        sender_email = cls.get_email_sender_for_package_type(package.package_type)
        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.package_type}")

        email_template_name = template_name or submit_constants.MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE
        if email_template_name == submit_constants.MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE:
            staff_email = current_app.config.get('STAFF_SUPPORT_MAIL_ID')
            if not staff_email:
                raise BadRequestError("STAFF_SUPPORT_MAIL_ID is not configured")

            recipients = [staff_email]
            submitted_on = package.submitted_on.strftime('%Y-%m-%d') if package.submitted_on else ''
            subject = f"SUBMISSION - {package.project_name} - {package.package_name} - {submitted_on}"
        else:
            recipients = [package.submitter_email]
            subject = f"Confirmation of receipt for {package.package_name}"

        email_details = EmailDetails(
            template_name=email_template_name,
            body_args={
                'project_name': package.project_name,
                'submitter_name': package.submitter_name,
                'submission_date': convert_utc_to_local_str(package.submitted_on) if package.submitted_on else '',
                'certificate_holder_name': package.proponent_name,
                'package_name': package.package_name,
                'documents': package.document_names,
            },
            subject=subject,
            sender=sender_email,
            recipients=recipients,
        )
        current_app.logger.info(
            "Sending email from %s to %s for package: %s",
            email_details.sender,
            ', '.join(email_details.recipients),
            email_details.body_args['package_name'],
        )
        return email_details

    @classmethod
    def prepare_awaiting_manager_approval_email(
        cls,
        package: PackageEmailData,
        manager_emails: list,
    ) -> EmailDetails:
        """Prepare email notifying managers that a package awaits approval."""
        sender_email = (
            cls.get_email_sender_for_package_type(package.package_type)
            or current_app.config.get('SENDER_EMAIL', '')
        )
        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.package_type}")

        return EmailDetails(
            template_name=submit_constants.SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE,
            body_args={
                'package_name': package.package_name,
                'project_name': package.project_name,
                'team_member_name': package.team_member_name,
            },
            subject=f"Submission awaiting Manager approval - {package.project_name} - {package.package_name}",
            sender=sender_email,
            recipients=manager_emails,
        )

    @staticmethod
    def get_email_sender_for_package_type(package_type: str) -> str:
        """Get the email sender for the package type."""
        return submit_constants.SUBMISSION_PACKAGE_TYPE_EMAIL_SENDER_MAP.get(package_type, None)

    @staticmethod
    def _require_submitter(package: PackageEmailData):
        if not package.submitter_name or not package.submitter_email:
            raise BadRequestError(f"Submitter for package {package.package_id} not found")
