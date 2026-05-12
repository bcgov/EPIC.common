from datetime import datetime

from epic_cron.models.external.condition_document import Document as ConditionDocumentModel
from epic_cron.models.external.condition_project import Project as ConditionProjectModel
from flask import current_app

from epic_cron.models.db import init_conditions_db, session_scope
from epic_cron.services.epic_public_service import EpicPublicService


class EpicPublicExtractor:
    """Task to sync document data from EPIC Public into the Condition Repo."""

    @classmethod
    def do_sync(cls):
        """Perform the sync from EPIC Public to the Condition Repo."""
        current_app.logger.info(f"Starting Stepped EPIC Public Extractor at {datetime.now()}")
        current_app.logger.info(
            "EPIC Public extractor config summary: base_url=%s search_path=%s type_ids=%s type_map=%s",
            current_app.config.get("EPIC_PUBLIC_BASE_URL"),
            current_app.config.get("EPIC_PUBLIC_SEARCH_PATH", "/api/public/search"),
            current_app.config.get("EPIC_PUBLIC_DOCUMENT_TYPE_IDS", ""),
            current_app.config.get("EPIC_PUBLIC_DOCUMENT_TYPE_ID_MAP", ""),
        )

        target_session = init_conditions_db(current_app)

        documents = EpicPublicService.fetch_all_documents()
        current_app.logger.info(f"Fetched {len(documents)} documents from EPIC Public.")
        cls._sync_documents(documents, target_session)

        current_app.logger.info(f"EPIC Public Stepped Extractor completed at {datetime.now()}")

    @classmethod
    def _sync_documents(cls, documents, target_session):
        """Insert new documents into the Condition Repo. Skips existing ones.

        Args:
            documents: List of mapped document dicts from EPIC Public.
            target_session: SQLAlchemy sessionmaker for the Condition DB.
        """
        current_app.logger.info(f"Syncing {len(documents)} documents to Condition Repo...")
        debug_logs_enabled = current_app.config.get("ENABLE_DETAILED_LOGS", False)
        inserted = 0
        skipped = 0
        failed = 0

        project_not_found = 0
        project_not_found_examples = []
        existing_examples = []

        with session_scope(target_session) as session:
            for doc in documents:
                try:
                    # Skip if the parent project hasn't been synced yet
                    project_exists = session.query(ConditionProjectModel).filter_by(
                        project_id=doc["project_id"]
                    ).first()
                    if not project_exists:
                        project_not_found += 1
                        if len(project_not_found_examples) < 10:
                            project_not_found_examples.append({
                                "document_id": doc["document_id"],
                                "project_id": doc["project_id"],
                            })
                        current_app.logger.debug(
                            f"Skipping document {doc['document_id']}: "
                            f"project {doc['project_id']} not found in Condition Repo."
                        )
                        continue

                    existing = session.query(ConditionDocumentModel).filter_by(
                        document_id=doc["document_id"]
                    ).first()

                    if existing:
                        skipped += 1
                        if len(existing_examples) < 10:
                            existing_examples.append(doc["document_id"])
                        continue

                    # Parse date_issued from ISO string
                    date_issued = None
                    if doc.get("date_issued"):
                        try:
                            date_issued = datetime.fromisoformat(
                                doc["date_issued"].replace("Z", "+00:00")
                            ).date()
                        except (ValueError, AttributeError):
                            current_app.logger.warning(
                                f"Could not parse date_issued for document {doc['document_id']}"
                            )

                    new_doc = ConditionDocumentModel(
                        document_id=doc["document_id"],
                        document_label=doc.get("document_label"),
                        document_file_name=doc.get("document_file_name"),
                        date_issued=date_issued,
                        act=doc.get("act"),
                        project_id=doc["project_id"],
                        document_type_id=doc.get("document_type_id"),
                        is_latest_amendment_added=False,
                        consultation_records_required=False,
                        is_active=False,
                        created_date=datetime.utcnow(),
                        updated_date=datetime.utcnow(),
                        created_by="cronjob",
                        updated_by="cronjob",
                    )
                    session.add(new_doc)
                    session.commit()
                    inserted += 1

                    if debug_logs_enabled:
                        current_app.logger.debug(
                            f"Inserted document: {doc['document_id']} - {doc.get('document_label')}"
                        )

                except Exception as e:
                    failed += 1
                    current_app.logger.error(f"Failed to sync document {doc.get('document_id')}: {e}")
                    session.rollback()

        current_app.logger.info(
            f"Document sync complete: {inserted} inserted, {skipped} skipped (existing), "
            f"{project_not_found} skipped (project not loaded), {failed} failed."
        )
        if project_not_found_examples:
            current_app.logger.info(
                "Sample documents skipped because project was not loaded: %s",
                project_not_found_examples,
            )
        if existing_examples:
            current_app.logger.info(
                "Sample existing documents skipped: %s",
                existing_examples,
            )
