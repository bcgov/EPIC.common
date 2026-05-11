"""Submit invitation email repository."""

from typing import Optional

from sqlalchemy import select

from epic_cron.data_classes.submit_email import InvitationEmailData
from epic_cron.repositories.submit_base import SubmitTableRepository


class SubmitInvitationRepository(SubmitTableRepository):
    """Read the Submit data needed to render invitation emails."""

    @staticmethod
    def _first_int(value) -> Optional[int]:
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            if item is None:
                continue
            try:
                return int(item)
            except (TypeError, ValueError):
                continue
        return None

    def get_email_data(self, invitation_id: int) -> Optional[InvitationEmailData]:
        invitations = self._table("invitations")
        roles = self._table("roles")

        stmt = (
            select(
                invitations.c.id,
                invitations.c.email,
                invitations.c.token,
                invitations.c.project_ids,
                invitations.c.package_ids,
                roles.c.role_name,
            )
            .select_from(
                invitations.outerjoin(roles, invitations.c.role_id == roles.c.id)
            )
            .where(invitations.c.id == invitation_id)
        )
        row = self.session.execute(stmt).mappings().first()
        if not row:
            return None

        project_name, proponent_name = self._find_invitation_project(
            row["project_ids"],
            row["package_ids"],
        )
        return InvitationEmailData(
            invitation_id=row["id"],
            email=row["email"],
            token=row["token"],
            role_name=row["role_name"],
            project_name=project_name,
            proponent_name=proponent_name,
        )

    def _find_invitation_project(self, project_ids, package_ids) -> tuple[str, str]:
        project_id = self._first_int(project_ids)
        if project_id:
            return self._find_project_by_id(project_id)

        package_id = self._first_int(package_ids)
        if package_id:
            return self._find_project_by_package_id(package_id)

        return "", ""

    def _find_project_by_id(self, project_id: int) -> tuple[str, str]:
        projects = self._table("projects")
        proponents = self._table("proponents")
        stmt = (
            select(
                projects.c.name.label("project_name"),
                proponents.c.name.label("proponent_name"),
            )
            .select_from(
                projects.outerjoin(proponents, projects.c.proponent_id == proponents.c.id)
            )
            .where(projects.c.id == project_id)
        )
        row = self.session.execute(stmt).mappings().first()
        if not row:
            return "", ""
        return row["project_name"] or "", row["proponent_name"] or ""

    def _find_project_by_package_id(self, package_id: int) -> tuple[str, str]:
        packages = self._table("packages")
        account_projects = self._table("account_projects")
        projects = self._table("projects")
        proponents = self._table("proponents")
        stmt = (
            select(
                projects.c.name.label("project_name"),
                proponents.c.name.label("proponent_name"),
            )
            .select_from(
                packages.join(
                    account_projects,
                    packages.c.account_project_id == account_projects.c.id,
                )
                .join(projects, account_projects.c.project_id == projects.c.id)
                .outerjoin(proponents, projects.c.proponent_id == proponents.c.id)
            )
            .where(packages.c.id == package_id)
        )
        row = self.session.execute(stmt).mappings().first()
        if not row:
            return "", ""
        return row["project_name"] or "", row["proponent_name"] or ""
