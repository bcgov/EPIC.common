from typing import Any, Dict, List

from submit_api.exceptions import BadRequestError

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.models.email_job import EmailJob


def _require(payload: Dict[str, Any], fields: List[str]) -> None:
    missing = [field for field in fields if field not in payload or payload.get(field) in (None, "")]
    if missing:
        raise BadRequestError(f"Missing required payload fields: {', '.join(missing)}")


def _build_subject(payload: Dict[str, Any]) -> str:
    report_type = payload["report_type"]
    report_month_label = payload["report_month_label"]
    total_actions = payload["summary"]["total_action_count"]
    all_clear = payload["all_clear"]

    if report_type == "followup":
        if all_clear:
            return f"EPIC SSL Follow-up for {report_month_label}: All clear"
        item_label = "item still needs attention" if total_actions == 1 else "items still need attention"
        return f"EPIC SSL Follow-up for {report_month_label}: {total_actions} {item_label}"

    if all_clear:
        return f"EPIC SSL Monthly Update for {report_month_label}: All clear"

    item_label = "item needs attention" if total_actions == 1 else "items need attention"
    return f"EPIC SSL Monthly Update for {report_month_label}: {total_actions} {item_label}"


def process_ssl_digest_notification(job: EmailJob) -> EmailDetails:
    """Build a friendly SSL monthly or follow-up digest email."""
    payload = job.payload or {}
    _require(
        payload,
        [
            "recipients",
            "sender",
            "centre_url",
            "generated_at",
            "report_type",
            "report_month_label",
            "all_clear",
            "summary",
            "items",
        ],
    )

    recipients = payload["recipients"]
    if not isinstance(recipients, list) or not recipients:
        raise BadRequestError("payload.recipients must be a non-empty list of email addresses")

    summary = payload["summary"]
    if not isinstance(summary, dict):
        raise BadRequestError("payload.summary must be an object")

    items = payload["items"]
    if not isinstance(items, list):
        raise BadRequestError("payload.items must be a list")

    return EmailDetails(
        template_name=job.template_name,
        body_args={
            "centre_url": payload["centre_url"],
            "generated_at": payload["generated_at"],
            "report_type": payload["report_type"],
            "report_month_label": payload["report_month_label"],
            "all_clear": payload["all_clear"],
            "summary": summary,
            "items": items,
        },
        subject=_build_subject(payload),
        sender=payload["sender"],
        recipients=recipients,
    )
