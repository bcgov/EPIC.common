from datetime import datetime
from enum import Enum

from flask import current_app

from epic_cron.models.db import init_submit_db, init_compliance_db, init_conditions_db
from epic_cron.models.external.compliance_project import Project as ComplianceProjectModel
from epic_cron.models.external.condition_project import Project as ConditionProjectModel
from epic_cron.models.external.submit import SubmitProject as SubmitProjectModel
from epic_cron.services.track_service import TrackService


class TargetSystem(Enum):
    SUBMIT = "SUBMIT"
    COMPLIANCE = "COMPLIANCE"
    CONDITIONS = "CONDITIONS"


class ProjectExtractor:
    """Sync Track projects into the selected target system."""

    @classmethod
    def do_sync(cls, target_system=TargetSystem.SUBMIT):
        """Fetch Track projects and upsert them into the target database."""
        current_app.logger.info(
            f"Starting Project Extractor for {target_system.value} at {datetime.now()}"
        )
        current_app.logger.info("Initializing database sessions...")

        target_session, target_model = cls._get_target_config(target_system)
        track_data = TrackService.fetch_track_projects()

        cls._upsert_into_target_db(track_data, target_session, target_model, target_system)

        current_app.logger.info(
            f"Project Extractor for {target_system.value} completed at {datetime.now()}"
        )

    @staticmethod
    def _get_target_config(target_system):
        """Return the session factory and model for the target system."""
        if target_system == TargetSystem.SUBMIT:
            return init_submit_db(current_app), SubmitProjectModel
        if target_system == TargetSystem.CONDITIONS:
            return init_conditions_db(current_app), ConditionProjectModel
        return init_compliance_db(current_app), ComplianceProjectModel

    @classmethod
    def _upsert_into_target_db(cls, track_data, target_session, target_model, target_system):
        """Upsert Track projects into the target database."""
        current_app.logger.info(
            f"Upserting records into the {target_system.value} database..."
        )

        successful_upserts = 0
        failed_upserts = 0
        updates = 0
        inserts = 0

        with target_session() as session:
            for index, row in enumerate(track_data):
                project = dict(row._mapping)
                current_app.logger.debug(
                    f"Upserting project {index + 1}/{len(track_data)}: {project}"
                )

                try:
                    result = cls._upsert_project(session, target_model, target_system, project)
                    if result == "inserted":
                        inserts += 1
                    elif result == "updated":
                        updates += 1

                    session.commit()
                    successful_upserts += 1
                except Exception as e:
                    failed_upserts += 1
                    current_app.logger.error(f"FAILED TO UPSERT PROJECT {project.get('id')}")
                    current_app.logger.error(f"Error Details: {e}")
                    current_app.logger.error(f"Failed Data: {project}")
                    session.rollback()

        current_app.logger.info(
            f"Summary: Upserted {successful_upserts} records "
            f"({inserts} inserts, {updates} updates) into {target_system.value} database."
        )
        if failed_upserts > 0:
            current_app.logger.warning(f"Summary: Failed to upsert {failed_upserts} records.")

    @classmethod
    def _upsert_project(cls, session, target_model, target_system, project):
        if target_system == TargetSystem.SUBMIT:
            return cls._upsert_submit_project(session, target_model, project)
        if target_system == TargetSystem.CONDITIONS:
            return cls._upsert_condition_project(session, target_model, project)
        return cls._upsert_compliance_project(session, target_model, project)

    @staticmethod
    def _upsert_submit_project(session, target_model, project):
        existing_project = session.query(target_model).filter_by(id=project["id"]).first()

        if existing_project:
            if project.get("is_deleted", False):
                session.delete(existing_project)
                current_app.logger.info(
                    f"Deleted project ID {project['id']} (marked as deleted in source)"
                )
                return None

            existing_project.name = project["name"]
            existing_project.epic_guid = project.get("epic_guid")
            existing_project.proponent_id = project.get("proponent_id")
            existing_project.ea_certificate = project.get("ea_certificate")
            current_app.logger.debug(f"Updated existing project ID {project['id']}")
            return "updated"

        project_instance = target_model(
            id=project["id"],
            name=project["name"],
            epic_guid=project.get("epic_guid"),
            proponent_id=project.get("proponent_id"),
            ea_certificate=project.get("ea_certificate"),
        )
        session.add(project_instance)
        current_app.logger.debug(f"Inserted new project ID {project['id']}")
        return "inserted"

    @staticmethod
    def _upsert_condition_project(session, target_model, project):
        condition_project_id = project.get("epic_guid") or str(project["id"])
        existing_project = (
            session.query(target_model)
            .filter_by(project_id=condition_project_id)
            .first()
        )

        if existing_project:
            if project.get("is_deleted", False):
                session.delete(existing_project)
                current_app.logger.info(
                    f"Deleted condition project {condition_project_id} "
                    "(marked as deleted in source)"
                )
                return None

            existing_project.project_name = project["name"]
            existing_project.project_type = (project.get("type_name") or "").strip()
            existing_project.updated_date = datetime.utcnow()
            existing_project.updated_by = "cronjob"
            current_app.logger.debug(
                f"Updated existing condition project {condition_project_id}"
            )
            return "updated"

        project_instance = target_model(
            project_id=condition_project_id,
            project_name=project["name"],
            project_type=(project.get("type_name") or "").strip(),
            created_date=datetime.utcnow(),
            updated_date=datetime.utcnow(),
            created_by="cronjob",
            updated_by="cronjob",
        )
        session.add(project_instance)
        current_app.logger.debug(f"Inserted new condition project {condition_project_id}")
        return "inserted"

    @staticmethod
    def _upsert_compliance_project(session, target_model, project):
        existing_project = session.query(target_model).filter_by(id=project["id"]).first()

        if existing_project:
            existing_project.name = project["name"]
            existing_project.updated_date = datetime.utcnow()
            existing_project.updated_by = "cronjob"
            existing_project.is_deleted = project.get("is_deleted", False)
            existing_project.is_active = project.get("is_active", True)
            current_app.logger.debug(
                f"Updated existing compliance project ID {project['id']} "
                f"(is_deleted={existing_project.is_deleted}, "
                f"is_active={existing_project.is_active})"
            )
            return "updated"

        project_instance = target_model(
            id=project["id"],
            name=project["name"],
            created_date=datetime.utcnow(),
            updated_date=datetime.utcnow(),
            created_by="cronjob",
            updated_by="cronjob",
            is_active=project.get("is_active", True),
            is_deleted=project.get("is_deleted", False),
        )
        session.add(project_instance)
        current_app.logger.debug(
            f"Inserted new compliance project ID {project['id']} "
            f"(is_deleted={project_instance.is_deleted}, "
            f"is_active={project_instance.is_active})"
        )
        return "inserted"
