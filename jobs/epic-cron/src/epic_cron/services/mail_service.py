"""Email service for Submit queued email payloads."""
from typing import Callable, Dict

from flask import current_app

from epic_cron.data_classes.email_details import EmailDetails
from epic_cron.exceptions import BadRequestError
from epic_cron.models.email_job import EmailJob
from epic_cron.repositories.email_repository import EmailRepository
from epic_cron.services.ches_service import ChesApiService
from epic_cron.services.template_renderer import TemplateRenderer


class EmailService:
    """Process Submit email queue rows without importing Submit models."""

    _processors: Dict[str, Callable[[EmailJob], EmailDetails]] = {}

    @classmethod
    def register_processor(cls, template_name: str, processor: Callable[[EmailJob], EmailDetails]):
        """Register a template-specific queue payload processor."""
        cls._processors[template_name] = processor

    @classmethod
    def process_email_queue(cls, repository: EmailRepository, limit: int = 100):
        """Fetch pending Submit emails, render them, and send them."""
        pending = repository.find_pending(limit=limit)
        if not pending:
            current_app.logger.info("No pending emails found.")
            return

        current_app.logger.info(f"Processing {len(pending)} pending Submit emails")
        for job in pending:
            try:
                processor = cls._get_processor(job)
                email_details = processor(job)
                cls.send_email(email_details)
                repository.mark_sent(job.id)
            except Exception as err:  # pylint: disable=broad-except
                current_app.logger.error(f"Error processing email {job.id}: {err}", exc_info=True)
                repository.mark_failed(job.id, str(err))

    @classmethod
    def _get_processor(cls, job: EmailJob) -> Callable[[EmailJob], EmailDetails]:
        if job.template_name not in cls._processors:
            raise BadRequestError(f"Unsupported email template: {job.template_name}")
        return cls._processors[job.template_name]

    @staticmethod
    def send_email(email_details: EmailDetails):
        """Render a Submit template and send it via CHES."""
        try:
            payload = TemplateRenderer.compose_email(
                email_details=email_details,
                domain='submit',
                web_url=current_app.config.get("WEB_URL", ""),
                environment=current_app.config.get("ENVIRONMENT", ""),
            )
            ches = ChesApiService()
            return ches.send_email(payload)
        except Exception as err:
            current_app.logger.error(f"Failed to send email: {err}", exc_info=True)
            raise BadRequestError("Failed to send email") from err
