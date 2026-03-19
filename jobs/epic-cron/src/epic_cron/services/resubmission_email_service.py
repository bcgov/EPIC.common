from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails
from submit_api.enums.role import RoleEnum
from submit_api.exceptions import BadRequestError
from submit_api.models.account_user import AccountUser as AccountUserModel
from submit_api.models.package import Package as PackageModel
from submit_api.models.role import Role as RoleModel
from submit_api.models.user_role import UserRole as UserRoleModel
from submit_api.utils.constants import MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE

from epic_cron.models import db


class ResubmissionEmailService:
    """Handles sending email notifications for resubmission requests."""

    @classmethod
    def get_project_admin_users(cls, package: PackageModel) -> list[AccountUserModel]:
        """Get all PROJECT_ADMIN and ACCOUNT_PRIMARY_ADMIN users for the package's account project."""
        account_project_id = package.account_project_id
        current_app.logger.info(f"Looking for admin users for account_project_id: {account_project_id}")

        admin_role_names = [RoleEnum.PROJECT_ADMIN.value, RoleEnum.ACCOUNT_PRIMARY_ADMIN.value]
        admin_roles = (
            db.session.query(RoleModel)
            .filter(RoleModel.role_name.in_(admin_role_names))
            .all()
        )
        if not admin_roles:
            raise BadRequestError("No admin roles found")

        admin_role_ids = [r.id for r in admin_roles]

        admin_users = (
            db.session.query(AccountUserModel)
            .join(UserRoleModel, AccountUserModel.id == UserRoleModel.account_user_id)
            .filter(
                UserRoleModel.account_project_id == account_project_id,
                UserRoleModel.role_id.in_(admin_role_ids),
                UserRoleModel.active
            )
            .all()
        )

        current_app.logger.info(f"Found {len(admin_users)} admin users for account_project_id: {account_project_id}")

        if not admin_users:
            current_app.logger.warning(f"No admin users found for account_project_id: {account_project_id}")
            raise BadRequestError("No admin users found for this account project")

        return admin_users

    @classmethod
    def prepare_resubmission_request_email(cls, package: PackageModel, project_admin_users: list[AccountUserModel]) -> EmailDetails:
        """Prepare email details for resubmission request for all project admin users."""
        if not package.submitted_by_user or not package.submitted_by_user.account_user:
            raise BadRequestError(f"Submitter with auth_guid {package.submitted_by} not found")
        web_url = current_app.config.get('WEB_URL')
        submission_link = f"{web_url}/proponent/projects/{package.account_project_id}/submission-packages/{package.id}"
        # Get all email addresses from project admin users
        recipient_emails = [user.work_email_address for user in project_admin_users]

        email_details = EmailDetails(
            template_name=MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE,
            body_args={
                'submission_link': submission_link,
                'package_name': package.name,
            },
            subject=f'Invitation to resubmit a new version of {package.name} in EPIC.submit',
            sender=current_app.config.get('SENDER_EMAIL'),
            recipients=recipient_emails,
        )

        return email_details
