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
QUARANTINE_FILE_PREFIX = ".virus-quarantine"


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

        result = SubmitVirusScanResult()
        try:
            clamav_service = ClamAVService()
            s3_service = S3Service()
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.exception("Unable to initialize virus scan services. Skipping scan. error=%s", exc)
            result.failed += 1
            return result

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
            current_app.logger.warning(
                "Virus detected but configured for report-only. submission_id=%s key=%s",
                submission.id,
                object_key,
            )
            return

        if action == VirusScanAction.QUARANTINE:
            cls._quarantine_submission(
                submission=submission,
                object_key=object_key,
                detection_details=detection_details,
                s3_service=s3_service,
            )
            result.rejected += 1
            result.quarantined += 1
        elif action == VirusScanAction.DELETE:
            cls._delete_submission_file(
                submission=submission,
                object_key=object_key,
                detection_details=detection_details,
                s3_service=s3_service,
            )
            result.rejected += 1
            result.deleted += 1
        else:
            cls._reject_submission(
                submission=submission,
                activity_message=(
                    f"{VIRUS_ACTIVITY_ACTION}. Detection: {detection_details}. "
                    "Action taken: rejected this upload."
                ),
            )
            db.session.commit()
            result.rejected += 1

    @staticmethod
    def _build_quarantine_key(object_key: str) -> str:
        """Build a quarantine object key in the same folder with a renamed file."""
        folder, separator, filename = object_key.rpartition("/")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        quarantined_name = f"{QUARANTINE_FILE_PREFIX}-{timestamp}-{filename}"
        if not separator:
            return quarantined_name
        return f"{folder}/{quarantined_name}"

    @staticmethod
    def _log_activity(submission: SubmissionModel, message: str):
        """Write a staff-only activity log entry for the submission."""
        ActivityLogService.log_activity(
            session=db.session,
            entity_id=submission.id,
            entity_type=ActivityTypeEnum.SUBMISSION.value,
            entity_version=submission.minor_version or 1,
            action=message,
            actor_id=VIRUS_ACTIVITY_ACTOR,
            actor_type=ActorTypeEnum.STAFF.value,
            visibility=VisibilityTypeEnum.STAFF.value,
        )

    @classmethod
    def _reject_submission(cls, submission: SubmissionModel, activity_message: str):
        """Mark the individual document submission as rejected and log why."""
        submission.status = SubmissionStatus.REJECTED
        db.session.add(submission)
        cls._log_activity(submission=submission, message=activity_message)

    @classmethod
    def _quarantine_submission(
        cls,
        submission: SubmissionModel,
        object_key: str,
        detection_details: str,
        s3_service: S3Service,
    ):
        """Rename the infected file in place and reject the upload if all steps succeed."""
        quarantine_key = cls._build_quarantine_key(object_key)
        s3_service.copy_object(object_key, quarantine_key)

        try:
            s3_service.delete_object(object_key)
        except Exception:
            cls._safe_delete_key(s3_service, quarantine_key)
            raise

        try:
            cls._reject_submission(
                submission=submission,
                activity_message=(
                    f"{VIRUS_ACTIVITY_ACTION}. Detection: {detection_details}. "
                    f"Action taken: quarantined infected file as {quarantine_key} and rejected this upload."
                ),
            )
            db.session.commit()
            current_app.logger.warning(
                "Infected file quarantined. submission_id=%s source_key=%s quarantine_key=%s",
                submission.id,
                object_key,
                quarantine_key,
            )
        except Exception:
            db.session.rollback()
            cls._restore_original_key(s3_service, quarantine_key, object_key)
            raise

    @classmethod
    def _delete_submission_file(
        cls,
        submission: SubmissionModel,
        object_key: str,
        detection_details: str,
        s3_service: S3Service,
    ):
        """Delete the infected file only if we can restore it on a later failure."""
        backup_key = cls._build_quarantine_key(object_key)
        s3_service.copy_object(object_key, backup_key)

        try:
            s3_service.delete_object(object_key)
        except Exception:
            cls._safe_delete_key(s3_service, backup_key)
            raise

        try:
            cls._reject_submission(
                submission=submission,
                activity_message=(
                    f"{VIRUS_ACTIVITY_ACTION}. Detection: {detection_details}. "
                    "Action taken: deleted infected file from S3 and rejected this upload."
                ),
            )
            db.session.commit()
            cls._safe_delete_key(s3_service, backup_key)
            current_app.logger.warning(
                "Infected file deleted. submission_id=%s key=%s",
                submission.id,
                object_key,
            )
        except Exception:
            db.session.rollback()
            cls._restore_original_key(s3_service, backup_key, object_key)
            raise

    @staticmethod
    def _safe_delete_key(s3_service: S3Service, object_key: str):
        """Best-effort delete for cleanup paths."""
        try:
            s3_service.delete_object(object_key)
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.warning("Cleanup delete failed for key=%s error=%s", object_key, exc)

    @staticmethod
    def _restore_original_key(s3_service: S3Service, source_key: str, destination_key: str):
        """Best-effort restore so submit is not affected by a later failure."""
        try:
            s3_service.copy_object(source_key, destination_key)
            s3_service.delete_object(source_key)
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.exception(
                "Failed to restore original S3 key after virus scan error. source_key=%s destination_key=%s error=%s",
                source_key,
                destination_key,
                exc,
            )

    @staticmethod
    def _get_action() -> str:
        """Return a validated virus scan action."""
        configured_action = (current_app.config.get("VIRUS_SCAN_ACTION") or VirusScanAction.QUARANTINE).upper()
        allowed_actions = {
            VirusScanAction.REPORT_ONLY,
            VirusScanAction.REJECT,
            VirusScanAction.QUARANTINE,
            VirusScanAction.DELETE,
        }
        if configured_action not in allowed_actions:
            raise ValueError(f"Invalid VIRUS_SCAN_ACTION: {configured_action}")
        return configured_action
