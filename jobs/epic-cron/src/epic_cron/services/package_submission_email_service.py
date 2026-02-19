
from flask import current_app
from submit_api.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError
from submit_api.models import AccountProject
from submit_api.models.account_user import AccountUser as AccountUserModel
from submit_api.models.package import Package as PackageModel
from submit_api.models.project import Project as ProjectModel
from submit_api.models.submission import SubmissionType
from submit_api.models.user import User as UserModel
from submit_api.enums.item_status import ItemStatus
from submit_api.models.submission_review_entry import SubmissionReviewEntryType
from submit_api.utils.constants import (
    MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE, MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE,
    SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE)

from epic_cron.models import db
from epic_cron.utils import constants
from epic_cron.utils.datetime import convert_utc_to_local_str


class PackageSubmissionEmailService:  # pylint: disable=too-few-public-methods
    """Handles sending email notifications for package submissions."""

    @classmethod
    def prepare_package_submission_email_confirmation(cls, package: PackageModel, template_name) -> EmailDetails:
        """Prepare email details for package submission confirmation."""
        submitter = cls._get_submitter(package.submitted_by)
        if not submitter:
            raise BadRequestError(f"Submitter with auth_guid {package.submitted_by} not found")

        sender_email = cls.get_email_sender_for_package_type(package.type.name)

        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.type.name}")

        account_project = cls._get_account_project_by_id(package.account_project_id)
        project = cls._get_project_by_id(account_project.project_id)
        if not project:
            raise BadRequestError(f"Project not found for account project ID: {account_project.id}")

        document_submissions = cls._get_document_submissions_from_package(package)
        email_template_name = template_name or MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE

        if email_template_name == MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE:
            staff_email = current_app.config.get('STAFF_SUPPORT_MAIL_ID')
            if not staff_email:
                raise BadRequestError("STAFF_SUPPORT_MAIL_ID is not configured")

            recipients = [staff_email]
            subject = f"SUBMISSION - {project.name} - {package.name} - {package.submitted_on.strftime('%Y-%m-%d')}"
        else:
            recipients = [submitter.work_email_address]
            subject = f"Confirmation of receipt for {package.name}"

        email_details = EmailDetails(
            template_name=email_template_name,
            body_args={
                'project_name': project.name,
                'submitter_name': submitter.full_name,
                'submission_date': convert_utc_to_local_str(package.submitted_on),
                'certificate_holder_name': project.proponent_name,
                'package_name': package.name,
                'documents': [submission.submitted_document.name for submission in document_submissions]
            },
            subject=subject,
            sender=sender_email,
            recipients=recipients,
        )
        current_app.logger.info(
            f"Sending email from {email_details.sender} to {', '.join(email_details.recipients)} for package: {email_details.body_args['package_name']}")

        return email_details

    @classmethod
    def prepare_awaiting_manager_approval_email(cls, package: PackageModel, manager_emails: list) -> EmailDetails:
        """Prepare email notifying MPT Managers that a package has been reviewed and awaits Manager's approval."""
        sender_email = cls.get_email_sender_for_package_type(package.type.name)
        if not sender_email:
            sender_email = current_app.config.get('SENDER_EMAIL', '')
        if not sender_email:
            raise BadRequestError(f"Sender email not found for package type: {package.type.name}")
        account_project = cls._get_account_project_by_id(package.account_project_id)
        project = cls._get_project_by_id(account_project.project_id)
        if not project:
            raise BadRequestError(f"Project not found for account project ID: {account_project.id}")
        team_member_name = cls._get_reviewer_name_for_awaiting_manager_package(package)
        subject = f"Submission awaiting Manager approval - {project.name} - {package.name}"
        email_details = EmailDetails(
            template_name=SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE,
            body_args={
                'package_name': package.name,
                'project_name': project.name,
                'team_member_name': team_member_name,
            },
            subject=subject,
            sender=sender_email,
            recipients=manager_emails,
        )
        return email_details

    @staticmethod
    def _get_reviewer_name_for_awaiting_manager_package(package: PackageModel) -> str:
        """Get the name of the team member who sent the package to Manager (from review STAFF_RECOMMENDATION)."""
        from submit_api.models.submission_review_entry import SubmissionReviewEntry
        awaiting_statuses = (
            ItemStatus.MP_AWAITING_MANAGER_APPROVAL,
            ItemStatus.CC_AWAITING_MANAGER_APPROVAL,
        )
        for item in package.items:
            if item.status not in awaiting_statuses:
                continue
            review = getattr(item, 'review', None) or next((r for r in item.reviews if r.active), None)
            if not review:
                continue
            entry = SubmissionReviewEntry.get_review_entry_by_id_and_type(
                review.id, SubmissionReviewEntryType.STAFF_RECOMMENDATION
            )
            if not entry or not entry.updated_by:
                continue
            user = entry.updated_by_user
            if user and getattr(user, 'staff_user', None) and user.staff_user:
                return user.staff_user.full_name or entry.updated_by
            return entry.updated_by
        return 'A team member'

    @staticmethod
    def get_email_sender_for_package_type(package_type: str) -> str:
        """Get the email sender for the package type."""
        return constants.SUBMISSION_PACKAGE_TYPE_EMAIL_SENDER_MAP.get(package_type, None)

    @staticmethod
    def _get_document_submissions_from_package(package: PackageModel):
        """Retrieve document submissions from the package."""
        submissions = [
            submission for item in package.items for submission in item.submissions
            if submission.type == SubmissionType.DOCUMENT
        ]
        return submissions

    @staticmethod
    def _get_submitter(auth_guid: str) -> AccountUserModel:
        """Retrieve the account user by their auth_guid."""
        return (
            db.session.query(AccountUserModel)
            .join(UserModel)
            .filter(UserModel.auth_guid == auth_guid)
            .first()
        )

    @staticmethod
    def _get_project_by_id(project_id: int) -> ProjectModel:
        """Retrieve the project by its ID."""
        return db.session.query(ProjectModel).filter(ProjectModel.id == project_id).first()

    @staticmethod
    def _get_account_project_by_id(id: int) -> AccountProject:
        """Retrieve the account project by its ID."""
        return db.session.query(AccountProject).filter(AccountProject.id == id).first()
