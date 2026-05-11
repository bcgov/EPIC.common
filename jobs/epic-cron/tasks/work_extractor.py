from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from epic_cron.models.db import init_submit_session
from epic_cron.models.external.track_work import TrackWork as TrackWorkModel
from epic_cron.services.track_service import TrackService


class WorkExtractor:
    """Sync Track work records into Submit."""

    @classmethod
    def do_sync(cls):
        """Fetch Track work data and upsert it into Submit."""
        current_app.logger.info(f"Starting Work Extractor at {datetime.now()}")
        current_app.logger.info("Initializing Submit database session...")
        session_factory = init_submit_session(current_app)

        current_app.logger.info("Fetching work data from Track API...")
        track_works = TrackService.fetch_track_works()
        current_app.logger.info(f"Fetched {len(track_works)} works from Track API")

        cls._upsert_works(track_works, session_factory)

        current_app.logger.info(f"Work Extractor completed at {datetime.now()}")

    @staticmethod
    def _upsert_works(track_works, session_factory):
        """Upsert work records into Submit."""
        total_works = len(track_works)
        inserts = 0
        updates = 0
        soft_deletes = 0
        skipped = 0
        failed = 0

        current_app.logger.info(
            f"Starting upsert of {total_works} works into Submit database..."
        )

        with session_factory() as session:
            for work in track_works:
                work_id = work.get("id")

                try:
                    existing_work = session.query(TrackWorkModel).filter_by(id=work_id).first()

                    if existing_work:
                        if work.get("is_deleted", False):
                            existing_work.is_deleted = True
                            existing_work.is_active = False
                            existing_work.updated_date = datetime.utcnow()
                            existing_work.updated_by = work.get("updated_by", "cronjob")
                            soft_deletes += 1
                            current_app.logger.info(
                                f"Soft deleted work ID {work_id}: {work.get('title')}"
                            )
                        else:
                            existing_work.project_id = work.get("project_id")
                            existing_work.current_phase_id = work.get("current_phase_id")
                            existing_work.work_state = work.get("work_state")
                            existing_work.title = work.get("title")
                            existing_work.is_active = work.get("is_active", True)
                            existing_work.is_deleted = work.get("is_deleted", False)
                            existing_work.updated_date = datetime.utcnow()
                            existing_work.updated_by = work.get("updated_by", "cronjob")
                            updates += 1
                            current_app.logger.debug(
                                f"Updated work ID {work_id}: {work.get('title')}"
                            )
                    else:
                        new_work = TrackWorkModel(
                            id=work_id,
                            project_id=work.get("project_id"),
                            current_phase_id=work.get("current_phase_id"),
                            work_state=work.get("work_state"),
                            title=work.get("title"),
                            is_active=work.get("is_active", True),
                            is_deleted=work.get("is_deleted", False),
                            created_date=datetime.utcnow(),
                            created_by=work.get("created_by", "cronjob"),
                            updated_by=work.get("updated_by", "cronjob"),
                        )
                        session.add(new_work)
                        inserts += 1
                        current_app.logger.debug(
                            f"Inserted new work ID {work_id}: {work.get('title')}"
                        )

                    session.commit()
                except IntegrityError as error:
                    session.rollback()
                    skipped += 1
                    error_detail = str(error.orig) if hasattr(error, "orig") else str(error)
                    current_app.logger.warning(
                        f"Foreign key constraint error for work ID {work_id} "
                        f"('{work.get('title')}'). Error: {error_detail}. "
                        f"Skipping this work. project_id={work.get('project_id')}, "
                        f"current_phase_id={work.get('current_phase_id')}"
                    )
                except Exception as error:
                    session.rollback()
                    failed += 1
                    current_app.logger.error(
                        f"Failed to upsert work ID {work_id} ('{work.get('title')}'): {error}"
                    )

        current_app.logger.info(
            f"Work upsert completed. Total: {total_works}, "
            f"Inserts: {inserts}, Updates: {updates}, Soft Deletes: {soft_deletes}, "
            f"Skipped (FK errors): {skipped}, Failed: {failed}"
        )
