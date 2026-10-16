"""Submit document queries for background security scanning."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, MetaData, String, Table, and_, insert, or_, select, update,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()

SCAN_RESULT_CLEAN = "CLEAN"
SCAN_RESULT_FAILED = "FAILED"
SCAN_RESULT_REJECTED = "REJECTED"

submitted_documents = Table(
    "submitted_documents", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("url", String),
    Column("created_date", DateTime),
    Column("updated_date", DateTime),
    Column("virus_scan_result", String),
)
submissions = Table(
    "submissions", metadata,
    Column("id", Integer, primary_key=True),
    Column("submitted_document_id", Integer),
    Column("item_id", Integer),
    Column("created_by", String),
    Column("deleted", Boolean),
)
items = Table(
    "items", metadata,
    Column("id", Integer, primary_key=True),
    Column("package_id", Integer),
)
packages = Table(
    "packages", metadata,
    Column("id", Integer, primary_key=True),
    Column("account_project_id", Integer),
    Column("name", String),
)
account_projects = Table(
    "account_projects", metadata,
    Column("id", Integer, primary_key=True),
    Column("account_id", Integer),
    Column("project_id", Integer),
)
projects = Table(
    "projects", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("proponent_id", Integer),
)
proponents = Table(
    "proponents", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("auth_guid", String),
)
account_users = Table(
    "account_users", metadata,
    Column("account_id", Integer),
    Column("user_id", Integer),
    Column("first_name", String),
    Column("last_name", String),
    Column("work_email_address", String),
)
email_queue = Table(
    "email_queue", metadata,
    Column("entity_id", Integer),
    Column("entity_type", String),
    Column("template_name", String),
    Column("status", String),
    Column("created_at", DateTime),
    Column("created_date", DateTime),
    Column("payload", JSONB),
)


class SubmitVirusScanRepository:
    """Persist scan results without importing Submit's application models."""

    def __init__(self, session):
        self.session = session

    def find_documents_to_scan(
        self,
        scan_cutoff: datetime,
        retry_cutoff: datetime,
        limit: int = 100,
    ):
        """Return new documents and failed documents whose retry delay has passed."""
        def uploader_value(column):
            return (
                select(column)
                .select_from(users.join(account_users, account_users.c.user_id == users.c.id))
                .where(
                    users.c.auth_guid == submissions.c.created_by,
                    account_users.c.account_id == account_projects.c.account_id,
                )
                .limit(1)
                .scalar_subquery()
            )

        uploader_name = uploader_value(
            account_users.c.first_name + " " + account_users.c.last_name
        )
        uploader_email = uploader_value(account_users.c.work_email_address)
        stmt = (
            select(
                submitted_documents.c.id,
                submitted_documents.c.name,
                submitted_documents.c.url,
                submitted_documents.c.created_date.label("uploaded_on"),
                packages.c.id.label("package_id"),
                packages.c.name.label("package_name"),
                account_projects.c.id.label("account_project_id"),
                projects.c.name.label("project_name"),
                proponents.c.name.label("proponent_name"),
                uploader_name.label("uploader_name"),
                uploader_email.label("uploader_email"),
            )
            .select_from(
                submitted_documents
                .join(submissions, submissions.c.submitted_document_id == submitted_documents.c.id)
                .join(items, items.c.id == submissions.c.item_id)
                .join(packages, packages.c.id == items.c.package_id)
                .join(account_projects, account_projects.c.id == packages.c.account_project_id)
                .join(projects, projects.c.id == account_projects.c.project_id)
                .join(proponents, proponents.c.id == projects.c.proponent_id)
            )
            .where(
                or_(
                    and_(
                        submitted_documents.c.virus_scan_result.is_(None),
                        submitted_documents.c.created_date <= scan_cutoff,
                    ),
                    and_(
                        submitted_documents.c.virus_scan_result == SCAN_RESULT_FAILED,
                        submitted_documents.c.updated_date <= retry_cutoff,
                    ),
                ),
                submissions.c.deleted.is_(False),
            )
            .order_by(submitted_documents.c.created_date)
            .limit(limit)
        )
        return [dict(row._mapping) for row in self.session.execute(stmt).all()]

    def mark_clean(self, document_id: int):
        """Mark a successfully scanned document as clean."""
        self.session.execute(
            update(submitted_documents)
            .where(
                submitted_documents.c.id == document_id,
                or_(
                    submitted_documents.c.virus_scan_result.is_(None),
                    submitted_documents.c.virus_scan_result == SCAN_RESULT_FAILED,
                ),
            )
            .values(virus_scan_result=SCAN_RESULT_CLEAN)
        )
        self.session.commit()

    def schedule_retry(self, document_ids: list[int]):
        """Delay another scan attempt without affecting document availability."""
        self.session.execute(
            update(submitted_documents)
            .where(
                submitted_documents.c.id.in_(document_ids),
                or_(
                    submitted_documents.c.virus_scan_result.is_(None),
                    submitted_documents.c.virus_scan_result == SCAN_RESULT_FAILED,
                ),
            )
            .values(virus_scan_result=SCAN_RESULT_FAILED, updated_date=datetime.now(UTC))
        )
        self.session.commit()

    def mark_rejected_and_queue_email(self, document: dict, payload: dict):
        """Record rejection and queue exactly one notification in one transaction."""
        result = self.session.execute(
            update(submitted_documents)
            .where(
                submitted_documents.c.id == document["id"],
                or_(
                    submitted_documents.c.virus_scan_result.is_(None),
                    submitted_documents.c.virus_scan_result == SCAN_RESULT_FAILED,
                ),
            )
            .values(virus_scan_result=SCAN_RESULT_REJECTED)
        )
        if result.rowcount == 1 and payload.get("recipients"):
            created_at = datetime.now(UTC)
            self.session.execute(insert(email_queue).values(
                entity_id=document["id"],
                entity_type="DOCUMENT",
                template_name="document_security_rejected.html",
                status="PENDING",
                created_at=created_at,
                created_date=created_at,
                payload=payload,
            ))
        self.session.commit()
