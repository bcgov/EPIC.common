"""Behavior tests for Submit email builders."""

from datetime import datetime

import pytest
from flask import Flask

from epic_cron.data_classes.submit_email import InvitationEmailData, PackageEmailData
from epic_cron.exceptions import BadRequestError
from epic_cron.services.invitation_email_service import InvitationEmailService
from epic_cron.services.package_submission_email_service import PackageSubmissionEmailService
from epic_cron.utils import submit_constants


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config.update(
        BC_SERVICE_CARD_URL="https://id.gov.bc.ca",
        LEGISLATIVE_TIMEZONE="US/Pacific",
        SENDER_EMAIL="noreply@example.com",
        SIGNUP_URL_PATH="/proponent/registration",
        STAFF_SUPPORT_MAIL_ID="staff@example.com",
        WEB_URL="https://submit.example.com",
    )
    return flask_app


def _package(**overrides):
    data = {
        "package_id": 7,
        "account_project_id": 11,
        "package_name": "Habitat Management Plan",
        "package_type": "Management Plan",
        "submitted_on": datetime(2026, 5, 1, 18, 30),
        "submitter_name": "Sam Submitter",
        "submitter_email": "sam@example.com",
        "project_name": "Sample Mine",
        "proponent_name": "Sample Holder",
        "document_names": ["plan.pdf"],
    }
    data.update(overrides)
    return PackageEmailData(**data)


def test_package_submission_confirmation_goes_to_submitter(app):
    with app.app_context():
        email = PackageSubmissionEmailService.prepare_package_submission_email_confirmation(
            _package()
        )

    assert email.template_name == submit_constants.MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE
    assert email.recipients == ["sam@example.com"]
    assert email.sender == "EAO.ManagementPlanSupport@gov.bc.ca"
    assert email.subject == "Confirmation of receipt for Habitat Management Plan"
    assert email.body_args["documents"] == ["plan.pdf"]


def test_package_staff_notification_goes_to_staff_support(app):
    with app.app_context():
        email = PackageSubmissionEmailService.prepare_package_submission_email_confirmation(
            _package(),
            submit_constants.MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE,
        )

    assert email.recipients == ["staff@example.com"]
    assert email.subject == "SUBMISSION - Sample Mine - Habitat Management Plan - 2026-05-01"


def test_invitation_uses_role_specific_action_text(app):
    invitation = InvitationEmailData(
        invitation_id=1,
        email="new.user@example.com",
        token="abc123",
        role_name=submit_constants.ROLE_SPECIFIC_SUBMISSION_CONTRIBUTOR,
        project_name="Sample Mine",
        proponent_name="Sample Holder",
    )

    with app.app_context():
        email = InvitationEmailService.prepare_invitation_email_notification(invitation)

    assert email.recipients == ["new.user@example.com"]
    assert email.body_args["invitation_action_text"] == "collaborate on"
    assert email.body_args["invitation_url"] == (
        "https://submit.example.com/proponent/registration?token=abc123"
    )


def test_invitation_requires_project_name(app):
    invitation = InvitationEmailData(
        invitation_id=1,
        email="new.user@example.com",
        token="abc123",
        role_name=submit_constants.ROLE_ACCOUNT_PRIMARY_ADMIN,
        project_name="",
        proponent_name="Sample Holder",
    )

    with app.app_context(), pytest.raises(BadRequestError):
        InvitationEmailService.prepare_invitation_email_notification(invitation)
