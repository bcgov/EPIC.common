"""Submit email queue repository."""

from datetime import datetime

from sqlalchemy import select, update

from epic_cron.data_classes.submit_email import SubmitEmailQueueEntry
from epic_cron.repositories.submit_base import SubmitTableRepository
from epic_cron.utils import submit_constants


class SubmitEmailQueueRepository(SubmitTableRepository):
    """Read and update Submit email queue rows."""

    def find_pending(self, limit=100) -> list[SubmitEmailQueueEntry]:
        email_queue = self._table("email_queue")
        stmt = (
            select(
                email_queue.c.id,
                email_queue.c.entity_id,
                email_queue.c.template_name,
            )
            .where(email_queue.c.status == submit_constants.EMAIL_STATUS_PENDING)
            .limit(limit)
        )
        rows = self.session.execute(stmt).mappings().all()
        return [
            SubmitEmailQueueEntry(
                id=row["id"],
                entity_id=row["entity_id"],
                template_name=row["template_name"],
            )
            for row in rows
        ]

    def mark_sent(self, email_id: int):
        email_queue = self._table("email_queue")
        stmt = (
            update(email_queue)
            .where(email_queue.c.id == email_id)
            .values(
                status=submit_constants.EMAIL_STATUS_SENT,
                error_message=None,
                sent_at=datetime.utcnow(),
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def mark_failed(self, email_id: int, error_message: str):
        email_queue = self._table("email_queue")
        stmt = (
            update(email_queue)
            .where(email_queue.c.id == email_id)
            .values(
                status=submit_constants.EMAIL_STATUS_FAILED,
                error_message=(error_message or "")[:500],
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def rollback(self):
        """Reset the current transaction before recording a failed email."""
        self.session.rollback()
