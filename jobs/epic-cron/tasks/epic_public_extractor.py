from datetime import datetime

from epic_cron.models.external.condition_document import Document as ConditionDocumentModel
from epic_cron.models.external.condition_document_type import DocumentType as ConditionDocumentTypeModel
from epic_cron.models.external.condition_project import Project as ConditionProjectModel
from flask import current_app
from sqlalchemy import func

from epic_cron.models.db import init_conditions_db, session_scope
from epic_cron.services.epic_public_service import EpicPublicService


class EpicPublicExtractor:
    """Task to sync document data from EPIC Public into the Condition Repo."""

    @classmethod
    def do_sync(cls):
        """Perform the sync from EPIC Public to the Condition Repo."""
        current_app.logger.info(f"Starting Stepped EPIC Public Extractor at {datetime.now()}")
        current_app.logger.info(
            "EPIC Public extractor config summary: base_url=%s search_path=%s type_map=%s default_type=%s",
            current_app.config.get("EPIC_PUBLIC_BASE_URL"),
            current_app.config.get("EPIC_PUBLIC_SEARCH_PATH", "/api/public/search"),
            current_app.config.get("EPIC_PUBLIC_DOCUMENT_TYPE_MAP", ""),
            current_app.config.get(
                "EPIC_PUBLIC_DEFAULT_DOCUMENT_TYPE",
                EpicPublicService.DEFAULT_DOCUMENT_TYPE_NAME,
            ),
        )

        target_session = init_conditions_db(current_app)

        source_type_to_document_type_id, default_document_type_id = cls._resolve_document_type_config(target_session)

        documents = EpicPublicService.fetch_all_documents(
            document_type_id_map=source_type_to_document_type_id,
            default_document_type_id=default_document_type_id,
        )
        current_app.logger.info(f"Fetched {len(documents)} documents from EPIC Public.")
        cls._sync_documents(documents, target_session)

        current_app.logger.info(f"EPIC Public Stepped Extractor completed at {datetime.now()}")

    @classmethod
    def _resolve_document_type_config(cls, target_session):
        """Resolve configured Condition document type names to database IDs once per run."""
        source_type_to_target_name = EpicPublicService.get_document_type_name_map()
        if not source_type_to_target_name:
            default_document_type_name = cls._get_default_document_type_name()
            if not default_document_type_name:
                raise ValueError("EPIC_PUBLIC_DEFAULT_DOCUMENT_TYPE is required when the type map is empty.")

            resolved_ids = cls._get_document_type_ids_by_name(target_session, [default_document_type_name])
            return {}, resolved_ids[default_document_type_name]

        document_type_names = list(source_type_to_target_name.values())
        resolved_ids = cls._get_document_type_ids_by_name(target_session, document_type_names)
        source_type_to_target_id = {
            source_type_id: resolved_ids[document_type_name]
            for source_type_id, document_type_name in source_type_to_target_name.items()
        }

        current_app.logger.info(
            "Resolved EPIC Public target document types: mapped_type_count=%s",
            len(source_type_to_target_id),
        )
        return source_type_to_target_id, None

    @classmethod
    def _get_default_document_type_name(cls):
        """Return the Condition document type name used when the source map is empty."""
        return str(current_app.config.get(
            "EPIC_PUBLIC_DEFAULT_DOCUMENT_TYPE",
            EpicPublicService.DEFAULT_DOCUMENT_TYPE_NAME,
        ) or "").strip()

    @classmethod
    def _get_document_type_ids_by_name(cls, target_session, document_type_names):
        """Look up Condition document_types.id values by stable document_type names."""
        normalized_names = {}
        for document_type_name in document_type_names:
            if not document_type_name or not document_type_name.strip():
                continue
            original_name = document_type_name.strip()
            normalized_names.setdefault(original_name.lower(), set()).add(original_name)

        if not normalized_names:
            return {}

        with session_scope(target_session) as session:
            rows = session.query(ConditionDocumentTypeModel).filter(
                func.lower(ConditionDocumentTypeModel.document_type).in_(list(normalized_names.keys()))
            ).all()

        resolved_ids = {}
        duplicate_names = set()
        for row in rows:
            normalized_name = row.document_type.strip().lower()
            if normalized_name in resolved_ids:
                duplicate_names.update(normalized_names[normalized_name])
            resolved_ids[normalized_name] = row.id

        missing_names = [
            original_name
            for normalized_name, original_names in normalized_names.items()
            for original_name in original_names
            if normalized_name not in resolved_ids
        ]
        if missing_names or duplicate_names:
            raise ValueError(
                "Invalid EPIC Public document type mapping. "
                f"Missing Condition document_types: {sorted(missing_names)}. "
                f"Duplicate Condition document_types: {sorted(duplicate_names)}."
            )

        return {
            original_name: resolved_ids[normalized_name]
            for normalized_name, original_names in normalized_names.items()
            for original_name in original_names
        }

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
