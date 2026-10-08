"""Passive virus scanning for EPIC.submit documents."""

from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from flask import current_app

from epic_cron.models.db import init_submit_session, session_scope
from epic_cron.repositories.submit_virus_scan_repository import SubmitVirusScanRepository
from epic_cron.services.clamav_service import ClamAVService
from epic_cron.services.document_storage_service import DocumentStorageService


class SubmitVirusScanService:
    """Scan uploads after a short access window without blocking submissions."""

    SCAN_DELAY = timedelta(minutes=5)
    RETRY_DELAY = timedelta(hours=1)

    @classmethod
    def run(cls):
        """Scan documents uploaded at least five minutes ago."""
        session_factory = init_submit_session(current_app)
        now = datetime.now(UTC)
        with session_scope(session_factory) as session:
            documents = SubmitVirusScanRepository(session).find_documents_to_scan(
                scan_cutoff=now - cls.SCAN_DELAY,
                retry_cutoff=now - cls.RETRY_DELAY,
            )

        current_app.logger.info("Found %s Submit documents for security scanning", len(documents))
        if not documents:
            return

        try:
            clamav = ClamAVService()
            storage = DocumentStorageService()
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.exception(
                "Security scanner setup failed; retrying in one hour: %s", exc
            )
            cls._schedule_retries(session_factory, documents)
            return

        for document in documents:
            cls._scan_document(session_factory, clamav, storage, document)

    @classmethod
    def _scan_document(cls, session_factory, clamav, storage, document):
        try:
            try:
                document_bytes = storage.read_bytes(document["url"])
            except ClientError as exc:
                if not storage.is_not_found(exc):
                    raise
                if cls._recover_quarantine(session_factory, storage, document):
                    return
                raise

            is_infected, scan_details = clamav.scan_bytes(document_bytes)
            if is_infected is None:
                raise RuntimeError(scan_details or "ClamAV returned an unknown result")

            with session_scope(session_factory) as session:
                repository = SubmitVirusScanRepository(session)
                if is_infected is False:
                    repository.mark_clean(document["id"])
                    current_app.logger.info("Security scan clean. document_id=%s", document["id"])
                    return

                quarantined_key = storage.quarantine(document["url"])
                repository.mark_rejected_and_queue_email(document, cls._email_payload(document))
                current_app.logger.warning(
                    "Document rejected by security scan. document_id=%s detection=%s "
                    "quarantined_key=%s",
                    document["id"], scan_details, quarantined_key,
                )
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.exception(
                "Security scan failed and will be retried in one hour. document_id=%s error=%s",
                document["id"], exc,
            )
            with session_scope(session_factory) as session:
                SubmitVirusScanRepository(session).schedule_retry([document["id"]])

    @classmethod
    def _record_rejection(cls, session_factory, document):
        """Persist rejection and its notification after quarantine succeeds."""
        with session_scope(session_factory) as session:
            SubmitVirusScanRepository(session).mark_rejected_and_queue_email(
                document, cls._email_payload(document)
            )

    @classmethod
    def _recover_quarantine(cls, session_factory, storage, document) -> bool:
        """Finalize the database update when an earlier S3 quarantine succeeded."""
        quarantined_key = storage.complete_started_quarantine(document["url"])
        if not quarantined_key:
            return False

        cls._record_rejection(session_factory, document)
        current_app.logger.warning(
            "Completed an earlier document quarantine. document_id=%s quarantined_key=%s",
            document["id"], quarantined_key,
        )
        return True

    @staticmethod
    def _schedule_retries(session_factory, documents):
        """Apply the retry delay to a batch after scanner setup fails."""
        with session_scope(session_factory) as session:
            document_ids = [document["id"] for document in documents]
            SubmitVirusScanRepository(session).schedule_retry(document_ids)

    @staticmethod
    def _email_payload(document):
        return {
            "sender": current_app.config.get("SENDER_EMAIL"),
            "recipients": [document["recipient"]] if document.get("recipient") else [],
            "subject": "Action required: A file in your EPIC.submit submission was rejected",
            "body_args": {
                "file_name": document["name"],
                "package_name": document["package_name"],
            },
            "cc": [],
            "bcc": [],
        }
