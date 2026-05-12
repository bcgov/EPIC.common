from datetime import datetime

from epic_cron.models.external.track_work import TrackWork as TrackWorkModel
from flask import current_app
from sqlalchemy.exc import IntegrityError

from epic_cron.models.db import init_submit_session, session_scope
from epic_cron.services.track_service import TrackService


class WorkExtractor:
    """Task to run EpicTrack Work Extraction."""

    @classmethod
    def do_sync(cls):
        """Perform the syncing of work data from Track API to Submit database."""
        current_app.logger.info(f"Starting Work Extractor at {datetime.now()}")

        # Initialize submit database session
        current_app.logger.info("Initializing Submit database session...")
        target_session = init_submit_session(current_app)

        try:
            # Step 1: Fetch work data from Track API
            current_app.logger.info("Fetching work data from Track API...")
            track_works = TrackService.fetch_track_works()
            current_app.logger.info(f"Fetched {len(track_works)} works from Track API")

            # Step 2: Upsert records into the submit database
            cls._upsert_works(track_works, target_session)

            current_app.logger.info(f"Work Extractor completed at {datetime.now()}")
        except Exception as e:
            current_app.logger.error(f"Error during work extraction: {e}")
            raise

    @staticmethod
    def _upsert_works(track_works, target_session):
        """
        Upsert work records into the submit database.
        
        Args:
            track_works: List of work dictionaries from Track API
            target_session: Database session for submit database
        """
        # Statistics tracking
        total_works = len(track_works)
        inserts = 0
        updates = 0
        soft_deletes = 0
        skipped = 0
        failed = 0

        current_app.logger.info(f"Starting upsert of {total_works} works into Submit database...")

        with session_scope(target_session) as session:
            for work_dict in track_works:
                work_id = work_dict.get("id")

                try:
                    existing_work = session.query(TrackWorkModel).filter_by(id=work_id).first()

                    if existing_work:
                        if work_dict.get("is_deleted", False):
                            existing_work.is_deleted = True
                            existing_work.is_active = False
                            existing_work.updated_date = datetime.utcnow()
                            existing_work.updated_by = work_dict.get("updated_by", "cronjob")
                            session.commit()
                            soft_deletes += 1
                            current_app.logger.info(f"Soft deleted work ID {work_id}: {work_dict.get('title')}")
                        else:
                            existing_work.project_id = work_dict.get("project_id")
                            existing_work.current_phase_id = work_dict.get("current_phase_id")
                            existing_work.work_state = work_dict.get("work_state")
                            existing_work.title = work_dict.get("title")
                            existing_work.is_active = work_dict.get("is_active", True)
                            existing_work.is_deleted = work_dict.get("is_deleted", False)
                            existing_work.updated_date = datetime.utcnow()
                            existing_work.updated_by = work_dict.get("updated_by", "cronjob")

                            session.commit()
                            updates += 1
                            current_app.logger.debug(f"Updated work ID {work_id}: {work_dict.get('title')}")
                    else:
                        new_work = TrackWorkModel(
                            id=work_dict.get("id"),
                            project_id=work_dict.get("project_id"),
                            current_phase_id=work_dict.get("current_phase_id"),
                            work_state=work_dict.get("work_state"),
                            title=work_dict.get("title"),
                            is_active=work_dict.get("is_active", True),
                            is_deleted=work_dict.get("is_deleted", False),
                            created_date=datetime.utcnow(),
                            created_by=work_dict.get("created_by", "cronjob"),
                            updated_by=work_dict.get("updated_by", "cronjob")
                        )
                        session.add(new_work)
                        session.commit()
                        inserts += 1
                        current_app.logger.debug(f"Inserted new work ID {work_id}: {work_dict.get('title')}")

                except IntegrityError as ie:
                    session.rollback()
                    skipped += 1
                    error_detail = str(ie.orig) if hasattr(ie, 'orig') else str(ie)
                    current_app.logger.warning(
                        f"Foreign key constraint error for work ID {work_id} ('{work_dict.get('title')}'). "
                        f"Error: {error_detail}. "
                        f"Skipping this work. project_id={work_dict.get('project_id')}, "
                        f"current_phase_id={work_dict.get('current_phase_id')}"
                    )
                except Exception as e:
                    session.rollback()
                    failed += 1
                    current_app.logger.error(
                        f"Failed to upsert work ID {work_id} ('{work_dict.get('title')}'): {e}"
                    )

        # Log summary
        current_app.logger.info(
            f"Work upsert completed. Total: {total_works}, "
            f"Inserts: {inserts}, Updates: {updates}, Soft Deletes: {soft_deletes}, "
            f"Skipped (FK errors): {skipped}, Failed: {failed}"
        )
