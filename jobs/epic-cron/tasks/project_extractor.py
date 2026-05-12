from datetime import datetime
from enum import Enum

from epic_cron.models.external.compliance_project import Project as ComplianceProjectModel
from epic_cron.models.external.condition_project import Project as ConditionProjectModel
from epic_cron.models.external.submit import SubmitProject
from flask import current_app

from epic_cron.models.db import init_submit_session, init_compliance_db, session_scope, \
    init_conditions_db  # Function that initializes DB engines
from epic_cron.services.track_service import TrackService


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

        # Step 1: Fetch data from track.projects
        track_data = TrackService.fetch_track_projects()

        # Step 2: Upsert records into the target database (update existing or insert new)
        cls._upsert_into_target_db(track_data, target_session, target_model, target_system)

        current_app.logger.info(f"Project Extractor for {target_system.value} completed at {datetime.now()}")

    @staticmethod
    def _get_target_config(target_system):
        """Get the target database session, model, and required fields based on the target system."""
        if target_system == TargetSystem.SUBMIT:
            return init_submit_session(current_app), SubmitProject
        if target_system == TargetSystem.CONDITIONS:
            return init_conditions_db(current_app), ConditionProjectModel
        return init_compliance_db(current_app), ComplianceProjectModel

    @staticmethod
    def _upsert_into_target_db(track_data, target_session, target_model, target_system):
        """Upsert (update or insert) records into the target database."""
        current_app.logger.info(f"Upserting records into the {target_system.value} database...")

        successful_upserts = 0
        failed_upserts = 0
        updates = 0
        inserts = 0
        
        with session_scope(target_session) as session:
            for index, row in enumerate(track_data):
                project_dict = dict(row._mapping)
                current_app.logger.debug(f"Upserting project {index + 1}/{len(track_data)}: {project_dict}")

                try:
                    if target_system == TargetSystem.SUBMIT:
                        existing_project = session.query(target_model).filter_by(id=project_dict["id"]).first()

                        if existing_project:
                            if project_dict.get("is_deleted", False):
                                session.delete(existing_project)
                                current_app.logger.info(
                                    f"Deleted project ID {project_dict['id']} (marked as deleted in source)"
                                )
                            else:
                                existing_project.name = project_dict["name"]
                                existing_project.epic_guid = project_dict.get("epic_guid")
                                existing_project.proponent_id = project_dict.get("proponent_id")
                                existing_project.ea_certificate = project_dict.get("ea_certificate")
                                updates += 1
                                current_app.logger.debug(f"Updated existing project ID {project_dict['id']}")
                        else:
                            project_instance = target_model(
                                id=project_dict["id"],
                                name=project_dict["name"],
                                epic_guid=project_dict.get("epic_guid"),
                                proponent_id=project_dict.get("proponent_id"),
                                ea_certificate=project_dict.get("ea_certificate"),
                            )
                            session.add(project_instance)
                            inserts += 1
                            current_app.logger.debug(f"Inserted new project ID {project_dict['id']}")
                    elif target_system == TargetSystem.CONDITIONS:
                        con_project_id = project_dict.get("epic_guid") or str(project_dict["id"])
                        existing_project = session.query(target_model).filter_by(project_id=con_project_id).first()

                        if existing_project:
                            if project_dict.get("is_deleted", False):
                                session.delete(existing_project)
                                current_app.logger.info(
                                    f"Deleted condition project {con_project_id} (marked as deleted in source)"
                                )
                            else:
                                existing_project.project_name = project_dict["name"]
                                existing_project.project_type = (project_dict.get("type_name") or "").strip()
                                existing_project.updated_date = datetime.utcnow()
                                existing_project.updated_by = "cronjob"
                                updates += 1
                                current_app.logger.debug(f"Updated existing condition project {con_project_id}")
                        else:
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
                        existing_project = session.query(target_model).filter_by(id=project_dict["id"]).first()

                        if existing_project:
                            existing_project.name = project_dict["name"]
                            existing_project.updated_date = datetime.utcnow()
                            existing_project.updated_by = "cronjob"
                            existing_project.is_deleted = project_dict.get("is_deleted", False)
                            existing_project.is_active = project_dict.get("is_active", True)
                            updates += 1
                            current_app.logger.debug(
                                f"Updated existing compliance project ID {project_dict['id']} "
                                f"(is_deleted={existing_project.is_deleted}, is_active={existing_project.is_active})"
                            )
                        else:
                            project_instance = target_model(
                                id=project_dict["id"],
                                name=project_dict["name"],
                                created_date=datetime.utcnow(),
                                updated_date=datetime.utcnow(),
                                created_by="cronjob",
                                updated_by="cronjob",
                                is_active=project_dict.get("is_active", True),
                                is_deleted=project_dict.get("is_deleted", False),
                            )
                            session.add(project_instance)
                            inserts += 1
                            current_app.logger.debug(
                                f"Inserted new compliance project ID {project_dict['id']} "
                                f"(is_deleted={project_instance.is_deleted}, is_active={project_instance.is_active})"
                            )

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
