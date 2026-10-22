"""Regression coverage for the staff security rejection notification."""
from datetime import UTC, datetime

from flask import Flask

from epic_cron.services.submit_virus_scan_service import SubmitVirusScanService
from epic_cron.services.template_renderer import TemplateRenderer


def test_security_notification_goes_to_system_support():
    """Route security alerts to system support and identify the regulated party."""
    app = Flask(__name__)
    app.config.update(
        STAFF_SUPPORT_MAIL_ID='management-plan@example.com',
        EPIC_SYSTEM_EMAIL='system-support@example.com',
        SENDER_EMAIL='submit@example.com',
        WEB_URL='https://submit.example.com',
    )
    document = {
        'id': 1,
        'name': 'plan.pdf',
        'project_name': 'Example project',
        'package_name': 'Example plan',
        'proponent_name': 'Example regulated party',
        'account_project_id': 2,
        'package_id': 3,
        'uploaded_on': datetime(2026, 10, 21, tzinfo=UTC),
    }
    with app.app_context():
        payload = SubmitVirusScanService._email_payload(document)

    assert payload['recipients'] == ['system-support@example.com']
    html = TemplateRenderer.render('document_security_rejected.html', payload['body_args'], 'submit')
    assert '<strong>Regulated Party:</strong> Example regulated party' in html
    assert '<strong>Proponent:</strong>' not in html
