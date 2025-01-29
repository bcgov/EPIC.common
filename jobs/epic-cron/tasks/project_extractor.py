from datetime import datetime
from enum import Enum

from compliance_api.models.project import Project as ComplianceProjectModel
from flask import current_app
from submit_api.models.project import Project as SubmitProjectModel

from epic_cron.models.db import init_db, init_submit_db, init_compliance_db  # Function that initializes DB engines
from epic_cron.services.track_service import TrackService


class TargetSystem(Enum):
    SUBMIT = "SUBMIT"
    COMPLIANCE = "COMPLIANCE"


class ProjectExtractor:
    """Task to run EpicTrack Project Extraction."""

    @classmethod
    def do_sync(cls, target_system=TargetSystem.SUBMIT):
        """Perform the syncing."""
        print(f"Starting Project Extractor for {target_system.value} at {datetime.now()}")

        # Initialize source and target database sessions
        print("Initializing database sessions...")

        target_session, target_model = cls._get_target_config(target_system)
        # Step 1: Fetch data from track.projects
        track_data = TrackService.fetch_track_data( )

        # Step 2: Clear the target database of existing records
        cls._clear_target_db(target_session, target_model, target_system)

        # Step 3: Insert new records into the target database
        cls._insert_into_target_db(track_data, target_session, target_model, target_system)

        print(f"Project Extractor for {target_system.value} completed at {datetime.now()}")

    @staticmethod
    def _get_target_config(target_system):
        """Get the target database session, model, and required fields based on the target system."""
        if target_system == TargetSystem.SUBMIT:
            return init_submit_db(current_app), SubmitProjectModel
        return init_compliance_db(current_app), ComplianceProjectModel

    @staticmethod
    def _clear_target_db(target_session, target_model, target_system):

        """
           Clear existing records in the target database for projects table.

           This method uses record-by-record deletion to handle dependency issues caused by foreign key constraints.
           Instead of bulk deletion, which might fail entirely, this approach ensures each record is processed
           individually. Records that cannot be deleted due to dependencies are logged for further analysis.
           """

        print(f"Preparing to clear existing records in the {target_system.value} database...")
        debug_logs_enabled = current_app.config.get("ENABLE_DETAILED_LOGS", False)

        # Initialize counters for summary
        total_records = 0
        failed_deletes = 0
        successful_deletes = 0
        failed_records = []

        # Iterate through each record and attempt deletion
        with target_session() as session:
            try:
                print(f"Fetching all records from the {target_system.value} database for deletion...")
                records = session.query(target_model).all()
                total_records = len(records)

                for record in records:
                    record_data = {col.name: getattr(record, col.name, None) for col in record.__table__.columns}

                    if debug_logs_enabled:
                        print(f"trying to  delete record: {record_data}")
                    try:
                        session.delete(record)
                        session.commit()  # Commit after each successful delete
                        successful_deletes += 1
                        if debug_logs_enabled:
                            print(f"trying to  delete record: {record_data}")
                    except Exception as delete_error:
                        failed_deletes += 1
                        failed_records.append({"record": record_data, "error": str(delete_error)})
                        print(f"WARNING: Could not delete record: {record_data}. Error: {delete_error}")
                        session.rollback()  # Rollback only this transaction

                print(f"Finished processing deletions in the {target_system.value} database.")
            except Exception as fetch_error:
                print(f"ERROR: Failed to fetch records from the {target_system.value} database. Error: {fetch_error}")
                session.rollback()

        # Print summary of the operation
        print(f"\nSummary of target database clearing for {target_system.value}:")
        print(f"- Total records found: {total_records}")
        print(f"- Records successfully deleted: {successful_deletes}")
        print(f"- Records failed to delete: {failed_deletes}")

        if failed_records:
            print("\nDetails of records that failed to delete:")
            for failed in failed_records:
                print(f"Record: {failed['record']}, Error: {failed['error']}")

        print("Summary: Clearing operation completed.")

    @staticmethod
    def _insert_into_target_db(track_data, target_session, target_model, target_system):
        """Insert new records into the target database."""
        print(f"Inserting new records into the {target_system.value} database...")

        with target_session() as session:
            successful_inserts = 0
            failed_inserts = 0
            for index, row in enumerate(track_data):
                project_dict = dict(row._mapping)
                debug_logs_enabled = current_app.config.get("ENABLE_DETAILED_LOGS", False)
                if debug_logs_enabled:
                    print(f"Inserting project {index + 1}/{len(track_data)}: {project_dict}")

                try:
                    if target_system == TargetSystem.SUBMIT:
                        project_instance = target_model(
                            name=project_dict['name'],
                            epic_guid=project_dict.get("epic_guid"),
                            proponent_id=project_dict.get("proponent_id"),
                            proponent_name=project_dict.get("proponent_name"),
                            ea_certificate=project_dict.get("ea_certificate")
                        )
                    else:
                        project_instance = target_model(
                            id=project_dict["id"],
                            name=project_dict['name'],
                            created_date=datetime.utcnow(),
                            updated_date=datetime.utcnow(),
                            created_by="cronjob",
                            updated_by="cronjob",
                            is_active=True,
                            is_deleted=False
                        )

                    session.add(project_instance)
                    session.commit()
                    successful_inserts += 1

                except Exception as e:
                    failed_inserts += 1
                    print(f"\n*** FAILED TO INSERT PROJECT {project_dict.get('id')} ***")
                    print(f"Error Details: {e}")
                    print(f"Failed Data: {project_dict}\n")
                    session.rollback()

            print(
                f"Summary: Inserted {successful_inserts} records successfully into the {target_system.value} database."
            )
            if failed_inserts > 0:
                print(f"Summary: Failed to insert {failed_inserts} records into the {target_system.value} database.")
