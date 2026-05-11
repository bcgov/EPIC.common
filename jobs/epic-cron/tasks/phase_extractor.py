from datetime import datetime

from flask import current_app

from epic_cron.models.db import init_submit_db
from epic_cron.models.external.track_phase import TrackPhase as TrackPhaseModel
from epic_cron.services.track_service import TrackService


class PhaseExtractor:
    """Sync Track phase records into Submit."""

    @classmethod
    def do_sync(cls):
        """Fetch Track phases and upsert them into Submit."""
        current_app.logger.info(f"Starting Phase Extractor at {datetime.now()}")
        current_app.logger.info("Initializing Submit database session...")
        session_factory = init_submit_db(current_app)

        current_app.logger.info("Fetching phase data from Track database...")
        track_phases = TrackService.fetch_track_phases()
        current_app.logger.info(f"Fetched {len(track_phases)} phases from Track database")

        cls._upsert_phases(track_phases, session_factory)

        current_app.logger.info(f"Phase Extractor completed at {datetime.now()}")

    @staticmethod
    def _upsert_phases(track_phases, session_factory):
        """Upsert phase records into Submit."""
        total_phases = len(track_phases)
        inserts = 0
        updates = 0
        soft_deletes = 0
        failed = 0

        current_app.logger.info(
            f"Starting upsert of {total_phases} phases into Submit database..."
        )

        with session_factory() as session:
            for phase in track_phases:
                phase_id = phase.get("id")

                try:
                    existing_phase = (
                        session.query(TrackPhaseModel)
                        .filter_by(id=phase_id)
                        .first()
                    )

                    if existing_phase:
                        if phase.get("is_deleted", False):
                            existing_phase.is_deleted = True
                            existing_phase.is_active = False
                            existing_phase.updated_date = datetime.utcnow()
                            existing_phase.updated_by = phase.get("updated_by", "cronjob")
                            soft_deletes += 1
                            current_app.logger.info(
                                f"Soft deleted phase ID {phase_id}: {phase.get('name')}"
                            )
                        else:
                            existing_phase.name = phase.get("name")
                            existing_phase.ea_act_id = phase.get("ea_act_id")
                            existing_phase.ea_act_name = phase.get("ea_act_name")
                            existing_phase.work_type_id = phase.get("work_type_id")
                            existing_phase.work_type_name = phase.get("work_type_name")
                            existing_phase.sort_order = phase.get("sort_order")
                            existing_phase.number_of_days = phase.get("number_of_days")
                            existing_phase.legislated = phase.get("legislated", False)
                            existing_phase.enable_submit = False
                            existing_phase.is_active = phase.get("is_active", True)
                            existing_phase.is_deleted = phase.get("is_deleted", False)
                            existing_phase.updated_date = datetime.utcnow()
                            existing_phase.updated_by = phase.get("updated_by", "cronjob")
                            updates += 1
                            current_app.logger.debug(
                                f"Updated phase ID {phase_id}: {phase.get('name')}"
                            )
                    else:
                        new_phase = TrackPhaseModel(
                            id=phase_id,
                            name=phase.get("name"),
                            display_name=phase.get("name"),
                            ea_act_id=phase.get("ea_act_id"),
                            ea_act_name=phase.get("ea_act_name"),
                            work_type_id=phase.get("work_type_id"),
                            work_type_name=phase.get("work_type_name"),
                            sort_order=phase.get("sort_order"),
                            number_of_days=phase.get("number_of_days"),
                            legislated=phase.get("legislated", False),
                            enable_submit=False,
                            is_active=phase.get("is_active", True),
                            is_deleted=phase.get("is_deleted", False),
                            created_date=datetime.utcnow(),
                            created_by=phase.get("created_by", "cronjob"),
                            updated_by=phase.get("updated_by", "cronjob"),
                        )
                        session.add(new_phase)
                        inserts += 1
                        current_app.logger.debug(
                            f"Inserted new phase ID {phase_id}: {phase.get('name')}"
                        )

                    session.commit()
                except Exception as error:
                    session.rollback()
                    failed += 1
                    current_app.logger.error(
                        f"Failed to upsert phase ID {phase_id} "
                        f"('{phase.get('name')}'): {error}"
                    )

        current_app.logger.info(
            f"Phase upsert completed. Total: {total_phases}, "
            f"Inserts: {inserts}, Updates: {updates}, Soft Deletes: {soft_deletes}, "
            f"Failed: {failed}"
        )
