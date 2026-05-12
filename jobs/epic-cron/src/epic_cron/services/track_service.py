from flask import current_app
from sqlalchemy import MetaData, Table, select, func

from epic_cron.models.db import init_db, session_scope


class TrackService:
    """Service to interact with the Track database."""

    @staticmethod
    def fetch_proponents():
        """Fetch and log unique proponents from the track.proponents table."""
        current_app.logger.info("Fetching proponents from track database...")

        track_session = init_db(current_app)
        with session_scope(track_session) as session:
            track_metadata = MetaData()
            track_proponents_table = Table('proponents', track_metadata, autoload_with=session.bind)

            current_app.logger.info("Selecting all proponents...")
            query = select(track_proponents_table.c.id, track_proponents_table.c.name)
            proponents_data = session.execute(query).fetchall()
            current_app.logger.info(f"Number of rows fetched from track.proponents: {len(proponents_data)}")
            
            for row in proponents_data:
                current_app.logger.debug(f"Fetched proponent: {dict(row._mapping)}")

        return proponents_data

    @staticmethod
    def fetch_track_projects():
        """Fetch and log data from the track.projects table, joining with proponents."""
        current_app.logger.info("Fetching data from track database...")

        required_fields = [
            "id", "name", "epic_guid", "proponent_name",
            "proponent_id", "ea_certificate", "type_name", "is_deleted", "is_active"
        ]

        track_session = init_db(current_app)
        with session_scope(track_session) as session:

            track_metadata = MetaData()
            track_projects_table = Table('projects', track_metadata, autoload_with=session.bind)
            track_proponents_table = Table('proponents', track_metadata, autoload_with=session.bind)
            track_types_table = Table('types', track_metadata, autoload_with=session.bind)

            current_app.logger.info(f"Selecting required fields: {required_fields} and joining with proponents...")
            # Join projects with proponents to get proponent name
            query = (
                select(
                    *[track_projects_table.c[field] for field in required_fields if field not in ("proponent_name", "type_name")],
                    track_proponents_table.c.name.label("proponent_name"),
                    func.coalesce(track_types_table.c.name, "").label("type_name")
                )
                .join(track_proponents_table, track_projects_table.c.proponent_id == track_proponents_table.c.id)
                .outerjoin(track_types_table, track_projects_table.c.type_id == track_types_table.c.id)
            )
            track_data = session.execute(query).fetchall()
            current_app.logger.info(f"Number of rows fetched from track.projects: {len(track_data)}")

            for row in track_data:
                current_app.logger.debug(f"Fetched row: {dict(row._mapping)}")

        return track_data

    @staticmethod
    def fetch_track_works():
        """
        Fetch work data from the Track database works table.

        Returns:
            List of work dictionaries with mapped fields for TrackWork model.
        """
        current_app.logger.info("Fetching works from track database...")

        track_session = init_db(current_app)
        with session_scope(track_session) as session:
            track_metadata = MetaData()
            works_table = Table('works', track_metadata, autoload_with=session.bind)
            projects_table = Table('projects', track_metadata, autoload_with=session.bind)
            work_types_table = Table('work_types', track_metadata, autoload_with=session.bind)
            work_phases_table = Table('work_phases', track_metadata, autoload_with=session.bind)

            current_app.logger.info("Selecting works with project, work type, and phase information...")
            # Query works and join with projects, work_types, and work_phases to generate title and get phase_id
            query = (
                select(
                    works_table.c.id,
                    works_table.c.project_id,
                    works_table.c.simple_title,
                    works_table.c.work_state,
                    works_table.c.is_active,
                    works_table.c.is_deleted,
                    projects_table.c.name.label("project_name"),
                    work_types_table.c.name.label("work_type_name"),
                    work_phases_table.c.phase_id.label("current_phase_id")
                )
                .join(
                    projects_table,
                    works_table.c.project_id == projects_table.c.id
                )
                .join(
                    work_types_table,
                    works_table.c.work_type_id == work_types_table.c.id
                )
                .outerjoin(
                    work_phases_table,
                    works_table.c.current_work_phase_id == work_phases_table.c.id
                )
            )
            
            works_data = session.execute(query).fetchall()
            current_app.logger.info(f"Number of rows fetched from track.works: {len(works_data)}")

            mapped_works = []
            for row in works_data:
                row_dict = dict(row._mapping)
                
                # Generate title using project_name, work_type_name, and simple_title
                project_name = row_dict.get("project_name", "")
                work_type_name = row_dict.get("work_type_name", "")
                simple_title = row_dict.get("simple_title", "")
                
                # Build title parts
                title_parts = [project_name, work_type_name]
                if simple_title:
                    title_parts.append(simple_title)
                generated_title = ' - '.join(title_parts)
                
                mapped_work = {
                    "id": row_dict.get("id"),
                    "project_id": row_dict.get("project_id"),
                    "current_phase_id": row_dict.get("current_phase_id"),
                    "work_state": row_dict.get("work_state"),
                    "title": generated_title,
                    "is_active": row_dict.get("is_active", True),
                    "is_deleted": row_dict.get("is_deleted", False),
                    "created_by": "cronjob",
                    "updated_by": "cronjob"
                }
                mapped_works.append(mapped_work)
                current_app.logger.debug(f"Fetched work: {mapped_work}")

            current_app.logger.info(f"Mapped {len(mapped_works)} works with required fields.")
            return mapped_works

    @staticmethod
    def fetch_track_phases():
        """
        Fetch phase data from the Track database phase_codes table.

        Returns:
            List of phase dictionaries with mapped fields for TrackPhase model.
        """
        current_app.logger.info("Fetching phases from track database...")

        track_session = init_db(current_app)
        with session_scope(track_session) as session:
            track_metadata = MetaData()
            phase_codes_table = Table('phase_codes', track_metadata, autoload_with=session.bind)
            work_types_table = Table('work_types', track_metadata, autoload_with=session.bind)
            ea_acts_table = Table('ea_acts', track_metadata, autoload_with=session.bind)

            current_app.logger.info("Selecting phases with work type and EA act information...")
            # Query phase_codes and join with work_types and ea_acts to get names
            query = (
                select(
                    phase_codes_table.c.id,
                    phase_codes_table.c.name,
                    phase_codes_table.c.ea_act_id,
                    phase_codes_table.c.work_type_id,
                    phase_codes_table.c.sort_order,
                    phase_codes_table.c.number_of_days,
                    phase_codes_table.c.legislated,
                    phase_codes_table.c.is_active,
                    phase_codes_table.c.is_deleted,
                    work_types_table.c.name.label("work_type_name"),
                    ea_acts_table.c.name.label("ea_act_name")
                )
                .outerjoin(
                    work_types_table,
                    phase_codes_table.c.work_type_id == work_types_table.c.id
                )
                .outerjoin(
                    ea_acts_table,
                    phase_codes_table.c.ea_act_id == ea_acts_table.c.id
                )
            )
            
            phases_data = session.execute(query).fetchall()
            current_app.logger.info(f"Number of rows fetched from track.phase_codes: {len(phases_data)}")

            mapped_phases = []
            for row in phases_data:
                row_dict = dict(row._mapping)
                mapped_phase = {
                    "id": row_dict.get("id"),
                    "name": row_dict.get("name"),
                    "display_name": row_dict.get("name"),  # Default to name
                    "ea_act_id": row_dict.get("ea_act_id"),
                    "ea_act_name": row_dict.get("ea_act_name"),
                    "work_type_id": row_dict.get("work_type_id"),
                    "work_type_name": row_dict.get("work_type_name"),
                    "sort_order": row_dict.get("sort_order"),
                    "number_of_days": row_dict.get("number_of_days"),
                    "legislated": row_dict.get("legislated", False),
                    "is_active": row_dict.get("is_active", True),
                    "is_deleted": row_dict.get("is_deleted", False),
                    "created_by": "cronjob",
                    "updated_by": "cronjob"
                }
                mapped_phases.append(mapped_phase)
                current_app.logger.debug(f"Fetched phase: {mapped_phase}")

            current_app.logger.info(f"Mapped {len(mapped_phases)} phases with required fields.")
            return mapped_phases
