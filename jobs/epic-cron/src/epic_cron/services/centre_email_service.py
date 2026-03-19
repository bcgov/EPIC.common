from typing import Callable, Dict

from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails
from submit_api.exceptions import BadRequestError

from epic_cron.models.email_job import EmailJob
from epic_cron.repositories.email_repository import EmailRepository
from epic_cron.services.ches_service import ChesApiService
from epic_cron.services.template_renderer import TemplateRenderer


class CentreEmailService:
    """Email service for Centre system, decoupled from submit_api models."""

    _processors: Dict[str, Callable[[EmailJob], EmailDetails]] = {}

    @classmethod
    def register_processor(cls, template_name: str, processor: Callable[[EmailJob], EmailDetails]):
        """Register a template-specific processor function."""
        cls._processors[template_name] = processor

    @classmethod
    def process_email_queue(cls, repository: EmailRepository, limit: int = 100):
        """Fetch and process pending emails using a repository."""
        pending = repository.find_pending(limit=limit)
        if not pending:
            current_app.logger.info("No pending emails found.")
            return

        current_app.logger.info(f"Processing {len(pending)} pending emails")

        for job in pending:
            try:
                processor = cls._get_processor(job)
                email_details = processor(job)
                cls.send_email(email_details)
                repository.mark_sent(job.id)
            except Exception as e:
                current_app.logger.error(f"Error processing email {job.id}: {e}", exc_info=True)
                repository.mark_failed(job.id, str(e))

    @classmethod
    def _get_processor(cls, job: EmailJob) -> Callable[[EmailJob], EmailDetails]:
        if job.template_name not in cls._processors:
            raise BadRequestError(f"Unsupported email template: {job.template_name}")
        return cls._processors[job.template_name]

    @staticmethod
    def send_email(email_details: EmailDetails):
        """Send email via CHES."""
        try:
            payload = TemplateRenderer.compose_email(
                email_details=email_details,
                domain='centre',
                web_url=current_app.config.get("WEB_URL", ""),
                environment=current_app.config.get("ENVIRONMENT", ""),
            )
            ches = ChesApiService()
            return ches.send_email(payload)
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {e}", exc_info=True)
            raise BadRequestError(f"Failed to send email")
