from urllib.parse import urljoin

from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.data_classes.submit_email import InvitationEmailData
from epic_cron.utils import submit_constants


class InvitationEmailService:  # pylint: disable=too-few-public-methods
    """Build email notifications for Submit invitations."""

    @classmethod
    def prepare_invitation_email_notification(cls, invitation: InvitationEmailData) -> EmailDetails:
        """Prepare email details for a new user invitation."""
        invitation_action_text = "join"
        if invitation.role_name == submit_constants.ROLE_ACCOUNT_PRIMARY_ADMIN:
            invitation_action_text = "manage"
        elif invitation.role_name == submit_constants.ROLE_SPECIFIC_SUBMISSION_CONTRIBUTOR:
            invitation_action_text = "collaborate on"

        if not invitation.project_name:
            raise BadRequestError(f"Project was not found for invitation id: {invitation.invitation_id}")

        return EmailDetails(
            template_name=submit_constants.NEW_USER_INVITATION_EMAIL_TEMPLATE,
            body_args={
                'epic_submit_link': current_app.config.get('WEB_URL'),
                'invitation_url': cls.generate_signup_url(invitation.token),
                'project_name': invitation.project_name,
                'bc_service_card_url': current_app.config.get('BC_SERVICE_CARD_URL', 'https://id.gov.bc.ca'),
                'certificate_holder_name': invitation.proponent_name,
                'invitation_action_text': invitation_action_text,
            },
            subject='Invitation to collaborate on EPIC.submit',
            sender=current_app.config.get('SENDER_EMAIL'),
            recipients=[invitation.email],
        )

    @staticmethod
    def generate_signup_url(token):
        """Generate a full URL with token for invitation."""
        base_url = current_app.config['WEB_URL']
        signup_path = current_app.config.get('SIGNUP_URL_PATH', '/proponent/registration')
        return urljoin(base_url, f"{signup_path}?token={token}")
