"""Regression coverage for the staff security rejection notification."""
from datetime import UTC, datetime, timedelta, timezone

from epic_cron.services.submit_virus_scan_service import SubmitVirusScanService
from epic_cron.services.template_renderer import TemplateRenderer

from flask import Flask

import pytest


@pytest.mark.parametrize(('uploaded_on', 'expected_date'), [
    (datetime(2026, 11, 18, 14, 38, tzinfo=UTC), '2026-11-18 07:38 AM PCT'),
    (datetime(2026, 11, 18, 14, 38), '2026-11-18 07:38 AM PCT'),
    (datetime(2026, 11, 19, 6, 59, tzinfo=UTC), '2026-11-18 11:59 PM PCT'),
    (datetime(2026, 11, 19, 7, tzinfo=UTC), '2026-11-19 12:00 AM PCT'),
    (datetime(2027, 1, 15, 14, 38, tzinfo=UTC), '2027-01-15 07:38 AM PCT'),
    (datetime(2027, 7, 15, 14, 38, tzinfo=UTC), '2027-07-15 07:38 AM PCT'),
    (datetime(2026, 11, 18, 19, 38, tzinfo=timezone(timedelta(hours=5))), '2026-11-18 07:38 AM PCT'),
])
def test_security_notification_goes_to_system_support(uploaded_on, expected_date):
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
        'uploaded_on': uploaded_on,
    }
    with app.app_context():
        payload = SubmitVirusScanService._email_payload(document)

    assert payload['recipients'] == ['system-support@example.com']
    assert payload['body_args']['uploaded_on'] == expected_date
    html = TemplateRenderer.render('document_security_rejected.html', payload['body_args'], 'submit')
    assert expected_date in html
    assert '<strong>Regulated Party:</strong> Example regulated party' in html
    assert '<strong>Proponent:</strong>' not in html
