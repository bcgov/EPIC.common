from datetime import datetime

from epic_cron.models.external.track_phase import TrackPhase as TrackPhaseModel
from flask import current_app

from epic_cron.models.db import init_submit_session, session_scope
from epic_cron.services.track_service import TrackService


class PhaseExtractor:
    """Task to run EpicTrack Phase Extraction - One-time sync."""

    @classmethod
    def do_sync(cls):
        """Perform the syncing of phase data from Track DB to Submit database."""
        current_app.logger.info(f"Starting Phase Extractor at {datetime.now()}")

        # Initialize submit database session
        current_app.logger.info("Initializing Submit database session...")
        target_session = init_submit_session(current_app)

        try:
            # Step 1: Fetch phase data from Track database
            current_app.logger.info("Fetching phase data from Track database...")
            track_phases = TrackService.fetch_track_phases()
            current_app.logger.info(f"Fetched {len(track_phases)} phases from Track database")

            # Step 2: Upsert records into the submit database
            cls._upsert_phases(track_phases, target_session)

            current_app.logger.info(f"Phase Extractor completed at {datetime.now()}")
        except Exception as e:
            current_app.logger.error(f"Error during phase extraction: {e}")
            raise

    @staticmethod
    def _upsert_phases(track_phases, target_session):
        """
        Upsert phase records into the submit database.
        
        Args:
            track_phases: List of phase dictionaries from Track database
            target_session: Database session for submit database
        """
        # Statistics tracking
        total_phases = len(track_phases)
        inserts = 0
        updates = 0
        soft_deletes = 0
        failed = 0

        current_app.logger.info(f"Starting upsert of {total_phases} phases into Submit database...")

        with session_scope(target_session) as session:
            for phase_dict in track_phases:
                phase_id = phase_dict.get("id")

                try:
                    existing_phase = session.query(TrackPhaseModel).filter_by(id=phase_id).first()

                    if existing_phase:
                        if phase_dict.get("is_deleted", False):
                            existing_phase.is_deleted = True
                            existing_phase.is_active = False
                            existing_phase.updated_date = datetime.utcnow()
                            existing_phase.updated_by = phase_dict.get("updated_by", "cronjob")
                            session.commit()
                            soft_deletes += 1
                            current_app.logger.info(f"Soft deleted phase ID {phase_id}: {phase_dict.get('name')}")
                        else:
                            existing_phase.name = phase_dict.get("name")
                            existing_phase.ea_act_id = phase_dict.get("ea_act_id")
                            existing_phase.ea_act_name = phase_dict.get("ea_act_name")
                            existing_phase.work_type_id = phase_dict.get("work_type_id")
                            existing_phase.work_type_name = phase_dict.get("work_type_name")
                            existing_phase.sort_order = phase_dict.get("sort_order")
                            existing_phase.number_of_days = phase_dict.get("number_of_days")
                            existing_phase.legislated = phase_dict.get("legislated", False)
                            existing_phase.enable_submit = False
                            existing_phase.is_active = phase_dict.get("is_active", True)
                            existing_phase.is_deleted = phase_dict.get("is_deleted", False)
                            existing_phase.updated_date = datetime.utcnow()
                            existing_phase.updated_by = phase_dict.get("updated_by", "cronjob")

                            session.commit()
                            updates += 1
                            current_app.logger.debug(f"Updated phase ID {phase_id}: {phase_dict.get('name')}")
                    else:
                        new_phase = TrackPhaseModel(
                            id=phase_dict.get("id"),
                            name=phase_dict.get("name"),
                            display_name=phase_dict.get("name"),
                            ea_act_id=phase_dict.get("ea_act_id"),
                            ea_act_name=phase_dict.get("ea_act_name"),
                            work_type_id=phase_dict.get("work_type_id"),
                            work_type_name=phase_dict.get("work_type_name"),
                            sort_order=phase_dict.get("sort_order"),
                            number_of_days=phase_dict.get("number_of_days"),
                            legislated=phase_dict.get("legislated", False),
                            enable_submit=False,
                            is_active=phase_dict.get("is_active", True),
                            is_deleted=phase_dict.get("is_deleted", False),
                            created_date=datetime.utcnow(),
                            created_by=phase_dict.get("created_by", "cronjob"),
                            updated_by=phase_dict.get("updated_by", "cronjob")
                        )
                        session.add(new_phase)
                        session.commit()
                        inserts += 1
                        current_app.logger.debug(f"Inserted new phase ID {phase_id}: {phase_dict.get('name')}")

                except Exception as e:
                    session.rollback()
                    failed += 1
                    current_app.logger.error(
                        f"Failed to upsert phase ID {phase_id} ('{phase_dict.get('name')}'): {e}"
                    )

        # Log summary
        current_app.logger.info(
            f"Phase upsert completed. Total: {total_phases}, "
            f"Inserts: {inserts}, Updates: {updates}, Soft Deletes: {soft_deletes}, "
            f"Failed: {failed}"
        )
