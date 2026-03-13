from typing import Any, Dict, List

from epic_cron.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError

from epic_cron.models.email_job import EmailJob


def _require(payload: Dict[str, Any], fields: List[str]) -> None:
    missing = [f for f in fields if not payload.get(f)]
    if missing:
        raise BadRequestError(f"Missing required payload fields: {', '.join(missing)}")


def process_access_granted(job: EmailJob) -> EmailDetails:
    """
    Processor for the 'access request submitted' template.

    Expected job.payload:
      {
        "recipients": ["user@example.com"],   # required
        "user_name": "Jane Doe",              # required
        "application_name": "EPIC.centre",    # required
        "sender": "staff@email.com",          # required (email address),
        "access_level": "VIEWER",
        "auth_link: "https://centre.example.com/request-access" # required
      }
    """
    payload = job.payload or {}
    _require(payload, ["recipients", "user_name", "application_name", "sender", "auth_link", "access_level"])

    recipients = payload["recipients"]
    if not isinstance(recipients, list) or not recipients:
        raise BadRequestError("payload.recipients must be a non-empty list of email addresses")

    subject = f"Your EPIC Access Request for {payload['application_name']} Has Been Granted"

    email_details = EmailDetails(
        template_name=job.template_name,
        body_args={
            'user_name': payload['user_name'],
            'application_name': payload['application_name'],
            'auth_link': payload['auth_link'],
            'access_level': payload['access_level']
        },
        subject=subject,
        sender=payload['sender'],
        recipients=recipients,
    )
    return email_details
