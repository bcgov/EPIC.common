from datetime import datetime
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from enum import Enum
from epic_cron.models.db import init_db, init_submit_db, init_compliance_db  # Function that initializes DB engines
from compliance_api.models.project import Project as ComplianceProjectModel
from submit_api.models.project import Project as SubmitProjectModel
from flask_sqlalchemy import SQLAlchemy
from flask import current_app
import logging

class TargetSystem(Enum):
    SUBMIT = "SUBMIT"
    COMPLIANCE = "COMPLIANCE"

class ProjectExtractor:
    """Task to run EpicTrack Project Extraction."""

    @classmethod
    def do_sync(cls, target_system=TargetSystem.SUBMIT):
        """Perform the ETL."""
        print(f"Starting Project Extractor for {target_system.value} at {datetime.now()}")

        # Initialize source and target database sessions
        print("Initializing database sessions...")
        track_session = init_db(current_app)
        target_session, target_model = cls._get_target_config(target_system)
        required_fields = ["id", "name", "epic_guid", "proponent_name","proponent_id","ea_certificate" ]
        # Step 1: Fetch data from track.projects
        cls._fetch_and_log_track_data(track_session, required_fields)

        # Step 2: Clear the target database of existing records
        cls._clear_target_db(target_session, target_model, target_system)

        # Step 3: Insert new records into the target database
        cls._insert_into_target_db(track_session, target_session, target_model, required_fields, target_system)

        print(f"Project Extractor for {target_system.value} completed at {datetime.now()}")

    @staticmethod
    def _get_target_config(target_system):
        """Get the target database session, model, and required fields based on the target system."""
        if target_system == TargetSystem.SUBMIT:
            return init_submit_db(current_app), SubmitProjectModel
        return init_compliance_db(current_app), ComplianceProjectModel

    @staticmethod
    def _fetch_and_log_track_data(track_session, required_fields):
        """Fetch and log data from the track.projects table, joining with proponents."""
        print("Fetching data from track database...")
        with track_session() as session:
            inspector = inspect(session.bind)
            print("Tables in the track database:")
            for table in inspector.get_table_names():
                print(f"- {table}")

            track_metadata = MetaData()
            track_projects_table = Table('projects', track_metadata, autoload_with=session.bind)
            track_proponents_table = Table('proponents', track_metadata, autoload_with=session.bind)

            print(f"Selecting required fields: {required_fields} and joining with proponents...")
            # Join projects with proponents to get proponent name
            query = (
                select(
                    *[track_projects_table.c[field] for field in required_fields if field != "proponent_name"],
                    track_proponents_table.c.name.label("proponent_name")
                )
                .join(track_proponents_table, track_projects_table.c.proponent_id == track_proponents_table.c.id)
            )
            track_data = session.execute(query).fetchall()
            print(f"Number of rows fetched from track.projects: {len(track_data)}")

            for row in track_data:
                print(f"Fetched row: {dict(row._mapping)}")

        return track_data

    @staticmethod
    def _clear_target_db(target_session, target_model, target_system):
        """Clear existing records in the target database."""
        print(f"Preparing to clear existing records in the {target_system.value} database...")
        with target_session() as session:
            try:
                print(f"Deleting all records from the {target_system.value} database")
                session.query(target_model).delete()
                session.commit()
                print(f"Deleted all existing records from the {target_system.value} database")
            except Exception as e:
                print(f"Error occurred while clearing the {target_system.value} database: {e}")
                session.rollback()

    @staticmethod
    def _insert_into_target_db(track_session, target_session, target_model, required_fields, target_system):
        """Insert new records into the target database."""
        print(f"Inserting new records into the {target_system.value} database...")
        track_data = ProjectExtractor._fetch_and_log_track_data(track_session, required_fields)

        with target_session() as session:
            for index, row in enumerate(track_data):
                project_dict = dict(row._mapping)
                print(f"Inserting project {index + 1}/{len(track_data)}: {project_dict}")

                try:
                    if target_system == TargetSystem.SUBMIT:
                        project_instance = target_model(
                            name=project_dict["name"],
                            epic_guid=project_dict.get("epic_guid"),
                            proponent_id=project_dict.get("proponent_id"),
                            proponent_name=project_dict.get("proponent_name"),
                            ea_certificate=project_dict.get("ea_certificate")

                        )
                    else:
                        project_instance = target_model(
                            id=project_dict["id"],
                            name=project_dict["name"],
                            created_date=datetime.utcnow(),
                            updated_date=datetime.utcnow(),
                            created_by="cronjob",
                            updated_by="cronjob",
                            is_active=True,
                            is_deleted=False
                        )

                    session.add(project_instance)
                    session.commit()

                except Exception as e:
                    print(f"\n*** FAILED TO INSERT PROJECT {project_dict['id']} ***")
                    print(f"Error Details: {e}")
                    print(f"Failed Data: {project_dict}\n")
                    session.rollback()

            print(f"Completed inserting projects into the {target_system.value} database.")