from urllib.parse import urljoin

from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails
from submit_api.enums.role import RoleEnum
from submit_api.exceptions import BadRequestError
from submit_api.models.account_project import AccountProject as AccountProjectModel
from submit_api.models.invitations import Invitations as InvitationsModel
from submit_api.models.package import Package as PackageModel
from submit_api.models.project import Project as ProjectModel
from submit_api.utils.constants import NEW_USER_INVITATION_EMAIL_TEMPLATE

from epic_cron.models import db


class InvitationEmailService:  # pylint: disable=too-few-public-methods
    """Handles sending email notifications for new user invitation."""

    @classmethod
    def prepare_invitation_email_notification(cls, invitation: InvitationsModel) -> EmailDetails:
        """Prepare email details for update request creation."""
        
        # Default action text
        invitation_action_text = "join"
        # Check role and modify invitation action text accordingly
        if invitation.role:
            if invitation.role.role_name == RoleEnum.ACCOUNT_PRIMARY_ADMIN.value:
                invitation_action_text = "manage"
            elif invitation.role.role_name == RoleEnum.SPECIFIC_SUBMISSION_CONTRIBUTOR.value:
                invitation_action_text = "collaborate on"

        bc_service_card_url = current_app.config.get('BC_SERVICE_CARD_URL', 'https://id.gov.bc.ca')

        if invitation.project_ids:
            project = cls.get_project_from_project_ids(invitation.project_ids)
        elif invitation.package_ids:
            project = cls.get_project_from_package_id(invitation.package_ids)
        else:
            raise BadRequestError("No project or package IDs provided in the invitation.")

        if not project:
            raise BadRequestError(f"Project was not found for invitation id: {invitation.id}")

        invitation_url = cls.generate_signup_url(invitation.token)

        email_details = EmailDetails(
            template_name=NEW_USER_INVITATION_EMAIL_TEMPLATE,
            body_args={
                'epic_submit_link': current_app.config.get('WEB_URL'),
                'invitation_url': invitation_url,
                'project_name': project.name or '',
                'bc_service_card_url': bc_service_card_url,
                'certificate_holder_name': (project.proponent.name if project.proponent else '') or '',
                'invitation_action_text': invitation_action_text,
            },
            subject='Invitation to collaborate on EPIC.submit',
            sender=current_app.config.get('SENDER_EMAIL'),
            recipients=[invitation.email],
        )

        return email_details

    @staticmethod
    def get_project_from_project_ids(project_ids: str) -> ProjectModel:
        """Return the first matching project from a list of project IDs."""
        project_id_list = [int(pid) for pid in project_ids if isinstance(pid, (int, str)) and str(pid).isdigit()]

        # assuming one project ID is provided in one invitation
        return (
            db.session.query(ProjectModel)
            .filter(ProjectModel.id.in_(project_id_list))
            .first()
        )

    @staticmethod
    def get_project_from_package_id(package_ids: list) -> ProjectModel:
        """Return the project linked to the first package ID."""
        if not isinstance(package_ids, list) or not package_ids:
            return None

        package_id = package_ids[0]

        # assuming only package ids of one project are provided in one invitation
        return (
            db.session.query(ProjectModel)
            .join(AccountProjectModel, ProjectModel.id == AccountProjectModel.project_id)
            .join(PackageModel, AccountProjectModel.id == PackageModel.account_project_id)
            .filter(PackageModel.id == package_id)
            .first()
        )

    @staticmethod
    def get_project_for_account_id(account_id: int) -> ProjectModel:
        """Return the first project for a given account ID."""
        if not account_id:
            return None

        return (
            db.session.query(ProjectModel)
            .join(AccountProjectModel, ProjectModel.id == AccountProjectModel.project_id)
            .filter(AccountProjectModel.account_id == account_id)
            .first()
        )

    @staticmethod
    def generate_signup_url(token):
        """Generate a full URL with token for invitation."""
        base_url = current_app.config['WEB_URL']
        signup_path = current_app.config.get('SIGNUP_URL_PATH', '/proponent/registration')

        # Construct the URL by joining base, path, and token
        return urljoin(base_url, f"{signup_path}?token={token}")
