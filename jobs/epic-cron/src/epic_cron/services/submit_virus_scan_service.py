"""Virus scanning workflow for EPIC.submit uploads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from flask import current_app
from submit_api.enums.activity_type import ActivityTypeEnum, ActorTypeEnum, VisibilityTypeEnum
from submit_api.services.activity_log_service import ActivityLogService
from submit_api.models.submission import Submission as SubmissionModel
from submit_api.models.submission import SubmissionStatus, SubmissionType
from submit_api.models.submitted_document import SubmittedDocument as SubmittedDocumentModel

from epic_cron.models import db
from epic_cron.services.clamav_service import ClamAVService
from epic_cron.services.s3_service import S3Service


class VirusScanAction:
    """Supported actions when an infected file is detected."""

    REPORT_ONLY = "REPORT_ONLY"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    DELETE = "DELETE"


VIRUS_ACTIVITY_ACTION = "Virus detected during overnight scan"
VIRUS_ACTIVITY_ACTOR = "epic.common-virus-scan"


@dataclass
class SubmitVirusScanResult:
    """Summary of a submit virus scan run."""

    scanned: int = 0
    clean: int = 0
    infected: int = 0
    rejected: int = 0
    quarantined: int = 0
    deleted: int = 0
    failed: int = 0
    skipped: int = 0


class SubmitVirusScanService:
    """Scan recent EPIC.submit uploads stored in S3."""

    @classmethod
    def scan_recent_uploads(cls) -> SubmitVirusScanResult:
        """Scan recent uploaded documents from EPIC.submit."""
        lookback_hours = current_app.config.get("VIRUS_SCAN_LOOKBACK_HOURS", 24)
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        return cls.scan_uploads_since(since)

    @classmethod
    def scan_uploads_since(cls, since: datetime) -> SubmitVirusScanResult:
        """Scan uploaded documents created on or after the supplied timestamp."""
        action = cls._get_action()

        current_app.logger.info(
            "Starting submit virus scan. since=%s action=%s",
            since.isoformat(),
            action,
        )

        clamav_service = ClamAVService()
        s3_service = S3Service()
        result = SubmitVirusScanResult()

        submissions = cls._find_recent_document_submissions(since=since)
        current_app.logger.info("Found %s submit documents to scan.", len(submissions))

        for submission in submissions:
            document = submission.submitted_document
            object_key = (document.url or "").strip() if document else ""

            if not object_key:
                result.skipped += 1
                current_app.logger.warning(
                    "Skipping submission %s because submitted document URL is empty.",
                    submission.id,
                )
                continue

            try:
                file_data = s3_service.read_bytes(object_key)
                infected, details = clamav_service.scan_bytes(file_data)
                result.scanned += 1

                if infected is False:
                    result.clean += 1
                    current_app.logger.info(
                        "Document scan clean. submission_id=%s document_id=%s key=%s",
                        submission.id,
                        document.id,
                        object_key,
                    )
                    continue

                if infected is True:
                    result.infected += 1
                    cls._handle_infected_submission(
                        submission=submission,
                        object_key=object_key,
                        detection_details=details,
                        action=action,
                        s3_service=s3_service,
                        result=result,
                    )
                    continue

                result.failed += 1
                current_app.logger.warning(
                    "Virus scan returned an unknown result. submission_id=%s document_id=%s key=%s details=%s",
                    submission.id,
                    document.id,
                    object_key,
                    details,
                )
            except Exception as exc:  # pylint: disable=broad-except
                result.failed += 1
                db.session.rollback()
                current_app.logger.exception(
                    "Failed to scan document. submission_id=%s document_id=%s key=%s error=%s",
                    submission.id,
                    document.id if document else None,
                    object_key,
                    exc,
                )

        current_app.logger.info("Completed submit virus scan. summary=%s", result)
        return result

    @classmethod
    def _find_recent_document_submissions(cls, since: datetime):
        """Return active document submissions created after the supplied timestamp."""
        query = (
            db.session.query(SubmissionModel)
            .join(SubmittedDocumentModel, SubmittedDocumentModel.id == SubmissionModel.submitted_document_id)
            .filter(
                SubmissionModel.type == SubmissionType.DOCUMENT,
                SubmissionModel.active.is_(True),
                SubmissionModel.deleted.is_(False),
                SubmissionModel.status != SubmissionStatus.REJECTED,
                SubmittedDocumentModel.created_date >= since,
            )
            .order_by(SubmittedDocumentModel.created_date.asc())
        )

        return query.all()

    @classmethod
    def _handle_infected_submission(
        cls,
        submission: SubmissionModel,
        object_key: str,
        detection_details: str,
        action: str,
        s3_service: S3Service,
        result: SubmitVirusScanResult,
    ):
        """Apply the configured action for an infected submission."""
        current_app.logger.warning(
            "Virus detected. submission_id=%s document_id=%s key=%s details=%s action=%s",
            submission.id,
            submission.submitted_document_id,
            object_key,
            detection_details,
            action,
        )

        if action == VirusScanAction.REPORT_ONLY:
            return

        submission.status = SubmissionStatus.REJECTED
        db.session.add(submission)
        ActivityLogService.log_activity(
            session=db.session,
            entity_id=submission.id,
            entity_type=ActivityTypeEnum.SUBMISSION.value,
            entity_version=submission.minor_version or 1,
            action=f"{VIRUS_ACTIVITY_ACTION}: {detection_details}",
            actor_id=VIRUS_ACTIVITY_ACTOR,
            actor_type=ActorTypeEnum.STAFF.value,
            visibility=VisibilityTypeEnum.STAFF.value,
        )
        result.rejected += 1

        if action == VirusScanAction.QUARANTINE:
            quarantine_key = cls._build_quarantine_key(object_key)
            s3_service.copy_object(object_key, quarantine_key)
            s3_service.delete_object(object_key)
            result.quarantined += 1
            current_app.logger.warning(
                "Infected file moved to quarantine. submission_id=%s source_key=%s quarantine_key=%s",
                submission.id,
                object_key,
                quarantine_key,
            )
        elif action == VirusScanAction.DELETE:
            s3_service.delete_object(object_key)
            result.deleted += 1
            current_app.logger.warning(
                "Infected file deleted from S3. submission_id=%s key=%s",
                submission.id,
                object_key,
            )

        db.session.commit()

    @staticmethod
    def _build_quarantine_key(object_key: str) -> str:
        """Build the quarantine object key while preserving the original path."""
        quarantine_prefix = current_app.config.get("VIRUS_SCAN_QUARANTINE_PREFIX", "quarantine/virus")
        quarantine_prefix = quarantine_prefix.strip().strip("/")
        return f"{quarantine_prefix}/{object_key.lstrip('/')}"

    @staticmethod
    def _get_action() -> str:
        """Return a validated virus scan action."""
        configured_action = (current_app.config.get("VIRUS_SCAN_ACTION") or VirusScanAction.REJECT).upper()
        allowed_actions = {
            VirusScanAction.REPORT_ONLY,
            VirusScanAction.REJECT,
            VirusScanAction.QUARANTINE,
            VirusScanAction.DELETE,
        }
        if configured_action not in allowed_actions:
            raise ValueError(f"Invalid VIRUS_SCAN_ACTION: {configured_action}")
        return configured_action
