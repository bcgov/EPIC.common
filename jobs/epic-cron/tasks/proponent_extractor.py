from datetime import datetime
from flask import current_app
from submit_api.models.proponent import Proponent as SubmitProponentModel
from epic_cron.models.db import init_submit_db
from epic_cron.services.track_service import TrackService


class ProponentExtractor:
    """Task to run EpicTrack Proponent Extraction."""

    @classmethod
    def do_sync(cls):
        """Perform the syncing."""
        print(f"Starting Proponent Extractor at {datetime.now()}")

        # Initialize target database session
        print("Initializing database sessions...")
        target_session = init_submit_db(current_app)

        proponents_data = TrackService.fetch_proponents()
        cls._sync_proponents(proponents_data, target_session, SubmitProponentModel)

        print(f"Proponent Extractor completed at {datetime.now()}")

    @staticmethod
    def _sync_proponents(track_proponents, target_session, target_model):
        """
        Synchronizes proponents between Source (Track) and Target (Submit).
        Strategy: Upsert (Insert/Update) + Soft Delete.
        """
        print(f"Syncing proponents into the SUBMIT database...")

        with target_session() as session:
            try:
                # Load all existing proponents to minimize DB round-trips
                existing_proponents = {p.id: p for p in session.query(target_model).all()}
                
                source_ids = set()
                count_updated = 0
                count_created = 0

                # 1. Update or Create Proponents from Source
                for row in track_proponents:
                    data = dict(row._mapping)
                    proponent_id = data["id"]
                    proponent_name = data["name"]
                    
                    source_ids.add(proponent_id)
                    
                    existing_record = existing_proponents.get(proponent_id)

                    if existing_record:
                        # TODO are there more different updates to proponens in track??
                        # Update if name changed or if it was previously deleted
                        if existing_record.name != proponent_name or existing_record.is_deleted:
                            existing_record.name = proponent_name
                            existing_record.is_deleted = False
                            count_updated += 1
                    else:
                        new_proponent = target_model(
                            id=proponent_id,
                            name=proponent_name,
                            is_deleted=False
                        )
                        session.add(new_proponent)
                        count_created += 1

                # 2. Soft Delete Proponents missing from track ..if track deleted some proponents
                count_deleted = 0
                for proponent_id, proponent in existing_proponents.items():
                    if proponent_id not in source_ids and not proponent.is_deleted:
                        print(f"Soft-deleting Proponent ID {proponent_id} (Missing in source)")
                        proponent.is_deleted = True
                        count_deleted += 1

                session.commit()
                
                print(f"Sync Complete: {count_created} Created, {count_updated} Updated, {count_deleted} Soft-Deleted.")
                
            except Exception as e:
                session.rollback()
                print(f"*** ERROR SYNCING PROPONENTS: {e} ***")
                raise e
