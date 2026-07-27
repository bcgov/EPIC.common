"""Service to synchronize staff work roles from EPIC.track to EPIC.submit."""
from flask import current_app
from sqlalchemy import MetaData, Table, select

from epic_cron.models.db import init_db, session_scope
from epic_cron.services.submit_api_service import SubmitApiService


class StaffWorkRoleSyncService:
    """Service to sync staff work roles from track to submit."""

    @staticmethod
    def fetch_active_staff_work_roles():
        """
        Fetch active staff work roles from track database with email addresses.
        
        Returns:
            List of dictionaries with work_id, email, and role_id
        """
        current_app.logger.info("Fetching active staff work roles from track database...")
        
        track_session = init_db(current_app)
        with session_scope(track_session) as session:
            track_metadata = MetaData()
            staff_work_roles_table = Table('staff_work_roles', track_metadata, autoload_with=session.bind)
            staffs_table = Table('staffs', track_metadata, autoload_with=session.bind)
            roles_table = Table('roles', track_metadata, autoload_with=session.bind)
            
            current_app.logger.info("Querying staff_work_roles with staff emails and role names...")
            query = (
                select(
                    staff_work_roles_table.c.id,
                    staff_work_roles_table.c.work_id,
                    staff_work_roles_table.c.staff_id,
                    staff_work_roles_table.c.role_id,
                    staffs_table.c.email,
                    roles_table.c.name.label("role_name")
                )
                .join(staffs_table, staff_work_roles_table.c.staff_id == staffs_table.c.id)
                .join(roles_table, staff_work_roles_table.c.role_id == roles_table.c.id)
                .where(staff_work_roles_table.c.is_deleted == False)
                .where(staff_work_roles_table.c.is_active == True)
                .where(staffs_table.c.is_deleted == False)
                .where(staffs_table.c.is_active == True)
            )
            
            staff_work_roles_data = session.execute(query).fetchall()
            current_app.logger.info(
                f"Number of active staff work roles fetched from track: {len(staff_work_roles_data)}"
            )
            
            mapped_roles = []
            for row in staff_work_roles_data:
                row_dict = dict(row._mapping)
                mapped_role = {
                    "id": row_dict.get("id"),
                    "work_id": row_dict.get("work_id"),
                    "staff_id": row_dict.get("staff_id"),
                    "role_id": row_dict.get("role_id"),
                    "email": row_dict.get("email"),
                    "role_name": row_dict.get("role_name")
                }
                mapped_roles.append(mapped_role)
                current_app.logger.debug(f"Fetched staff work role: {mapped_role}")
            
            current_app.logger.info(f"Mapped {len(mapped_roles)} staff work roles with required fields.")
            return mapped_roles

    @staticmethod
    def map_track_role_to_submit_role(role_id: int) -> str:
        """
        Map track role_id to submit role string.
        
        Args:
            role_id: Role ID from track database
            
        Returns:
            "TEAM_LEAD" or "TEAM_MEMBER"
        """
        # TEAM_LEAD (role_id=2) maps to "TEAM_LEAD"
        # All others map to "TEAM_MEMBER"
        if role_id == 2:
            return "TEAM_LEAD"
        return "TEAM_MEMBER"


    @classmethod
    def sync_staff_work_roles_to_submit(cls):
        """
        Synchronize staff work roles from track to submit via API.
        
        This method:
        1. Fetches active staff work roles from track database
        2. Fetches existing staff user works from submit API
        3. Compares and determines what needs to be created/updated/deleted
        4. Calls submit API to perform the changes
        """
        current_app.logger.info("Starting staff work role synchronization...")
        
        # 1. Fetch active staff work roles from track
        track_staff_work_roles = cls.fetch_active_staff_work_roles()
        
        # Group by (email, work_id) to handle multiple roles per staff/work
        # Priority: TEAM_LEAD > TEAM_MEMBER
        track_email_work_map = {}
        for role_data in track_staff_work_roles:
            email = role_data["email"]
            work_id = role_data["work_id"]
            role_id = role_data["role_id"]
            
            key = (email, work_id)
            submit_role = cls.map_track_role_to_submit_role(role_id)
            
            # If key exists, keep TEAM_LEAD if either is TEAM_LEAD
            if key in track_email_work_map:
                existing_role = track_email_work_map[key]
                if existing_role == "TEAM_LEAD" or submit_role == "TEAM_LEAD":
                    track_email_work_map[key] = "TEAM_LEAD"
            else:
                track_email_work_map[key] = submit_role
        
        current_app.logger.info(
            f"Grouped into {len(track_email_work_map)} unique email+work_id combinations from track"
        )
        
        # 2. Fetch existing staff user works from submit API
        try:
            existing_staff_user_works = SubmitApiService.get_staff_user_works()
        except Exception as e:
            current_app.logger.error(f"Failed to fetch existing staff user works: {e}")
            return {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "deleted": 0,
                "failed": 0
            }
        
        # Build map of existing active staff user works
        submit_email_work_map = {}
        for work in existing_staff_user_works:
            if work.get('is_active'):
                email = work.get('email')
                work_id = work.get('work_id')
                role = work.get('role')
                if email and work_id:
                    submit_email_work_map[(email, work_id)] = role
        
        current_app.logger.info(
            f"Found {len(submit_email_work_map)} active staff user works in submit"
        )
        
        # 3. Determine what needs to be created/updated/deleted
        to_sync = []
        to_delete = []
        
        # Find items to sync (in track but not in submit, or role changed)
        for (email, work_id), track_role in track_email_work_map.items():
            submit_role = submit_email_work_map.get((email, work_id))
            if submit_role is None or submit_role != track_role:
                # Doesn't exist or role changed - sync it
                to_sync.append((email, work_id, track_role))
        
        # Find items to delete (in submit but not in track)
        for (email, work_id), submit_role in submit_email_work_map.items():
            if (email, work_id) not in track_email_work_map:
                to_delete.append((email, work_id))
        
        current_app.logger.info(
            f"Changes needed - Sync: {len(to_sync)}, Delete: {len(to_delete)}"
        )
        
        # 4. Execute changes via API
        synced_count = 0
        deleted_count = 0
        failed_count = 0
        
        # Sync (create or update)
        for email, work_id, role in to_sync:
            try:
                current_app.logger.debug(
                    f"Syncing: email={email}, work_id={work_id}, role={role}"
                )
                SubmitApiService.create_or_update_staff_user_work(
                    email=email,
                    work_id=work_id,
                    role=role
                )
                synced_count += 1
            except Exception as e:
                failed_count += 1
                current_app.logger.error(
                    f"Failed to sync staff work role for email={email}, work_id={work_id}: {e}"
                )
        
        # Delete (deactivate)
        for email, work_id in to_delete:
            try:
                current_app.logger.debug(
                    f"Delete: email={email}, work_id={work_id}"
                )
                SubmitApiService.delete_staff_user_work(
                    work_id=work_id
                )
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                current_app.logger.error(
                    f"Failed to delete staff work role for email={email}, work_id={work_id}: {e}"
                )
        
        current_app.logger.info(
            f"Staff work role sync completed. "
            f"Synced: {synced_count}, Deleted: {deleted_count}, Failed: {failed_count}"
        )
        
        return {
            "processed": len(to_sync) + len(to_delete),
            "synced": synced_count,
            "deleted": deleted_count,
            "failed": failed_count
        }
