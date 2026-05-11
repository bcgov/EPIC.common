from typing import List

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from epic_cron.models.email_job import EmailJob


metadata = MetaData()

# Local definition of the table (decoupled from submit_api.models)
email_queue_table = Table(
    "email_queue",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("template_name", String(255), nullable=False),
    Column("status", String(32), nullable=False, server_default="PENDING"),
    Column("payload", JSONB, nullable=False),  # everything template-specific lives here
    Column("error_message", Text, nullable=True),
    Column("sent_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class EmailRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_pending(self, limit=100) -> List[EmailJob]:
        stmt = (
            select(email_queue_table)
            .where(email_queue_table.c.status == "PENDING")
            .limit(limit)
        )
        rows = self.session.execute(stmt).fetchall()
        return [
            EmailJob(
                id=row.id,
                template_name=row.template_name,
                status=row.status,
                payload=row.payload,
                error_message=row.error_message,
                sent_at=row.sent_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def mark_sent(self, email_id: int):
        stmt = (
            email_queue_table.update()
            .where(email_queue_table.c.id == email_id)
            .values(status="SENT", error_message=None, payload=None, sent_at=func.now())
        )
        self.session.execute(stmt)
        self.session.commit()

    def mark_failed(self, email_id: int, error_message: str):
        stmt = (
            email_queue_table.update()
            .where(email_queue_table.c.id == email_id)
            .values(status="FAILED", error_message=error_message, sent_at=func.now())
        )
        self.session.execute(stmt)
        self.session.commit()
