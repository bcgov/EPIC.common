from datetime import datetime
from enum import Enum

from epic_cron.models.external.compliance_project import Project as ComplianceProjectModel
from epic_cron.models.external.condition_project import Project as ConditionProjectModel
from flask import current_app
from submit_api.models.project import Project as SubmitProjectModel

from epic_cron.models.db import init_db, init_submit_db, init_compliance_db, \
    init_conditions_db  # Function that initializes DB engines
from epic_cron.services.track_service import TrackService
from tasks.proponent_status_updater import ProponentStatusUpdater


class TargetSystem(Enum):
    SUBMIT = "SUBMIT"
    COMPLIANCE = "COMPLIANCE"
    CONDITIONS = "CONDITIONS"


class ProjectExtractor:
    """Task to run EpicTrack Project Extraction."""

    @classmethod
    def do_sync(cls, target_system=TargetSystem.SUBMIT):
        """Perform the syncing."""
        current_app.logger.info(f"Starting Project Extractor for {target_system.value} at {datetime.now()}")

        # Initialize source and target database sessions
        current_app.logger.info("Initializing database sessions...")

        target_session, target_model = cls._get_target_config(target_system)
        
        try:
            # Step 1: Fetch data from track.projects
            track_data = TrackService.fetch_track_data()

            # Step 2: Upsert records into the target database (update existing or insert new)
            cls._upsert_into_target_db(track_data, target_session, target_model, target_system)
            # Step 3: Proponent Status Update (Only for SUBMIT)
            if target_system == TargetSystem.SUBMIT:
                ProponentStatusUpdater.update(target_session, target_model)

            current_app.logger.info(f"Project Extractor for {target_system.value} completed at {datetime.now()}")
        finally:
            # Cleanup session based on type
            if target_system == TargetSystem.SUBMIT:
                # Flask-SQLAlchemy cleanup
                from epic_cron.models import db
                db.session.remove()
            # Raw SQLAlchemy sessions are cleaned up in helper methods with context managers

    @staticmethod
    def _get_target_config(target_system):
        """Get the target database session, model, and required fields based on the target system."""
        if target_system == TargetSystem.SUBMIT:
            return init_submit_db(current_app), SubmitProjectModel
        if target_system == TargetSystem.CONDITIONS:
            return init_conditions_db(current_app), ConditionProjectModel
        return init_compliance_db(current_app), ComplianceProjectModel

    @staticmethod
    def _clear_target_db(target_session, target_model, target_system):

        """
           Clear existing records in the target database for projects table.

           This method uses record-by-record deletion to handle dependency issues caused by foreign key constraints.
           Instead of bulk deletion, which might fail entirely, this approach ensures each record is processed
           individually. Records that cannot be deleted due to dependencies are logged for further analysis.
           """

        current_app.logger.info(f"Preparing to clear existing records in the {target_system.value} database...")

        # Initialize counters for summary
        total_records = 0
        failed_deletes = 0
        successful_deletes = 0
        failed_records = []

        # Handle Flask-SQLAlchemy vs raw SQLAlchemy differently
        if target_system == TargetSystem.SUBMIT:
            # Flask-SQLAlchemy - use db.session directly
            from epic_cron.models import db
            session = db.session
            try:
                current_app.logger.info(f"Fetching all records from the {target_system.value} database for deletion...")
                records = session.query(target_model).all()
                total_records = len(records)

                for record in records:
                    record_data = {col.name: getattr(record, col.name, None) for col in record.__table__.columns}

                    current_app.logger.debug(f"trying to  delete record: {record_data}")
                    try:
                        session.delete(record)
                        session.commit()  # Commit after each successful delete
                        successful_deletes += 1
                        current_app.logger.debug(f"successfully deleted record: {record_data}")
                    except Exception as delete_error:
                        failed_deletes += 1
                        failed_records.append({"record": record_data, "error": str(delete_error)})
                        current_app.logger.warning(f"Could not delete record: {record_data}. Error: {delete_error}")
                        session.rollback()  # Rollback only this transaction

                current_app.logger.info(f"Finished processing deletions in the {target_system.value} database.")
            except Exception as fetch_error:
                current_app.logger.error(f"Failed to fetch records from the {target_system.value} database. Error: {fetch_error}")
                session.rollback()
        else:
            # Raw SQLAlchemy - use context manager
            with target_session() as session:
                try:
                    current_app.logger.info(f"Fetching all records from the {target_system.value} database for deletion...")
                    records = session.query(target_model).all()
                    total_records = len(records)

                    for record in records:
                        record_data = {col.name: getattr(record, col.name, None) for col in record.__table__.columns}

                        current_app.logger.debug(f"trying to  delete record: {record_data}")
                        try:
                            session.delete(record)
                            session.commit()  # Commit after each successful delete
                            successful_deletes += 1
                            current_app.logger.debug(f"successfully deleted record: {record_data}")
                        except Exception as delete_error:
                            failed_deletes += 1
                            failed_records.append({"record": record_data, "error": str(delete_error)})
                            current_app.logger.warning(f"Could not delete record: {record_data}. Error: {delete_error}")
                            session.rollback()  # Rollback only this transaction

                    current_app.logger.info(f"Finished processing deletions in the {target_system.value} database.")
                except Exception as fetch_error:
                    current_app.logger.error(f"Failed to fetch records from the {target_system.value} database. Error: {fetch_error}")
                    session.rollback()

        # Print summary of the operation
        current_app.logger.info(f"Summary of target database clearing for {target_system.value}:")
        current_app.logger.info(f"- Total records found: {total_records}")
        current_app.logger.info(f"- Records successfully deleted: {successful_deletes}")
        current_app.logger.info(f"- Records failed to delete: {failed_deletes}")

        if failed_records:
            current_app.logger.warning("Details of records that failed to delete:")
            for failed in failed_records:
                current_app.logger.warning(f"Record: {failed['record']}, Error: {failed['error']}")

        current_app.logger.info("Summary: Clearing operation completed.")

    @staticmethod
    def _upsert_into_target_db(track_data, target_session, target_model, target_system):
        """Upsert (update or insert) records into the target database."""
        current_app.logger.info(f"Upserting records into the {target_system.value} database...")

        successful_upserts = 0
        failed_upserts = 0
        updates = 0
        inserts = 0
        
        # Handle Flask-SQLAlchemy vs raw SQLAlchemy differently
        if target_system == TargetSystem.SUBMIT:
            # Flask-SQLAlchemy - use db.session directly
            from epic_cron.models import db
            session = db.session
            
            for index, row in enumerate(track_data):
                project_dict = dict(row._mapping)
                current_app.logger.debug(f"Upserting project {index + 1}/{len(track_data)}: {project_dict}")

                try:
                    # Query for existing project
                    existing_project = session.query(target_model).filter_by(id=project_dict["id"]).first()
                    
                    if existing_project:
                        # Check if project is deleted at source
                        if project_dict.get("is_deleted", False):
                            # Delete from target if deleted at source
                            session.delete(existing_project)
                            current_app.logger.info(f"Deleted project ID {project_dict['id']} (marked as deleted in source)")
                        else:
                            # Update existing record
                            existing_project.name = project_dict['name']
                            existing_project.epic_guid = project_dict.get("epic_guid")
                            existing_project.proponent_id = project_dict.get("proponent_id")
                            existing_project.ea_certificate = project_dict.get("ea_certificate")
                            updates += 1
                            current_app.logger.debug(f"Updated existing project ID {project_dict['id']}")
                    else:
                        # Insert new record
                        project_instance = target_model(
                            id=project_dict["id"],
                            name=project_dict['name'],
                            epic_guid=project_dict.get("epic_guid"),
                            proponent_id=project_dict.get("proponent_id"),
                            ea_certificate=project_dict.get("ea_certificate")
                        )
                        session.add(project_instance)
                        inserts += 1
                        current_app.logger.debug(f"Inserted new project ID {project_dict['id']}")

                    session.commit()
                    successful_upserts += 1

                except Exception as e:
                    failed_upserts += 1
                    current_app.logger.error(f"FAILED TO UPSERT PROJECT {project_dict.get('id')}")
                    current_app.logger.error(f"Error Details: {e}")
                    current_app.logger.error(f"Failed Data: {project_dict}")
                    session.rollback()

            current_app.logger.info(
                f"Summary: Upserted {successful_upserts} records ({inserts} inserts, {updates} updates) into {target_system.value} database."
            )
            if failed_upserts > 0:
                current_app.logger.warning(f"Summary: Failed to upsert {failed_upserts} records.")
        else:
            # Raw SQLAlchemy - use context manager
            with target_session() as session:
                for index, row in enumerate(track_data):
                    project_dict = dict(row._mapping)
                    current_app.logger.debug(f"Upserting project {index + 1}/{len(track_data)}: {project_dict}")

                    try:
                        if target_system == TargetSystem.CONDITIONS:
                            # con repo uses epic_guid as project_id
                            con_project_id = project_dict.get("epic_guid") or str(project_dict["id"])
                            
                            # Query for existing project
                            existing_project = session.query(target_model).filter_by(project_id=con_project_id).first()
                            
                            if existing_project:
                                # Check if project is deleted at source
                                if project_dict.get("is_deleted", False):
                                    # Delete from target if deleted at source
                                    session.delete(existing_project)
                                    current_app.logger.info(f"Deleted condition project {con_project_id} (marked as deleted in source)")
                                else:
                                    # Update existing record
                                    existing_project.project_name = project_dict["name"]
                                    existing_project.project_type = (project_dict.get("type_name") or "").strip()
                                    existing_project.updated_date = datetime.utcnow()
                                    existing_project.updated_by = "cronjob"
                                    updates += 1
                                    current_app.logger.debug(f"Updated existing condition project {con_project_id}")
                            else:
                                # Insert new record
                                project_instance = target_model(
                                    project_id=con_project_id,
                                    project_name=project_dict["name"],
                                    project_type=(project_dict.get("type_name") or "").strip(),
                                    created_date=datetime.utcnow(),
                                    updated_date=datetime.utcnow(),
                                    created_by="cronjob",
                                    updated_by="cronjob",
                                )
                                session.add(project_instance)
                                inserts += 1
                                current_app.logger.debug(f"Inserted new condition project {con_project_id}")
                        else:
                            # Compliance system
                            # Query for existing project
                            existing_project = session.query(target_model).filter_by(id=project_dict["id"]).first()
                            
                            if existing_project:
                                # Update existing record - sync ALL fields including is_deleted and is_active
                                existing_project.name = project_dict['name']
                                existing_project.updated_date = datetime.utcnow()
                                existing_project.updated_by = "cronjob"
                                # Sync is_deleted and is_active from source
                                existing_project.is_deleted = project_dict.get("is_deleted", False)
                                existing_project.is_active = project_dict.get("is_active", True)
                                updates += 1
                                current_app.logger.debug(f"Updated existing compliance project ID {project_dict['id']} (is_deleted={existing_project.is_deleted}, is_active={existing_project.is_active})")
                            else:
                                # Insert new record - use values from source
                                project_instance = target_model(
                                    id=project_dict["id"],
                                    name=project_dict['name'],
                                    created_date=datetime.utcnow(),
                                    updated_date=datetime.utcnow(),
                                    created_by="cronjob",
                                    updated_by="cronjob",
                                    is_active=project_dict.get("is_active", True),
                                    is_deleted=project_dict.get("is_deleted", False)
                                )
                                session.add(project_instance)
                                inserts += 1
                                current_app.logger.debug(f"Inserted new compliance project ID {project_dict['id']} (is_deleted={project_instance.is_deleted}, is_active={project_instance.is_active})")

                        session.commit()
                        successful_upserts += 1

                    except Exception as e:
                        failed_upserts += 1
                        current_app.logger.error(f"FAILED TO UPSERT PROJECT {project_dict.get('id')}")
                        current_app.logger.error(f"Error Details: {e}")
                        current_app.logger.error(f"Failed Data: {project_dict}")
                        session.rollback()

                current_app.logger.info(
                    f"Summary: Upserted {successful_upserts} records ({inserts} inserts, {updates} updates) into {target_system.value} database."
                )
                if failed_upserts > 0:
                    current_app.logger.warning(f"Summary: Failed to upsert {failed_upserts} records.")
