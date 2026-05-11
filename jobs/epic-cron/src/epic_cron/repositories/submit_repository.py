"""Small Submit database gateway used by epic-cron."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import MetaData, Table, select, update

from epic_cron.utils import constants


@dataclass
class SubmitEmailQueueEntry:
    """A pending Submit email queue row."""

    id: int
    entity_id: int
    template_name: str


@dataclass
class PackageEmailData:
    """Package details needed to render Submit emails."""

    package_id: int
    account_project_id: int
    package_name: str
    package_type: str
    submitted_on: Optional[datetime]
    submitter_name: str
    submitter_email: str
    project_name: str
    proponent_name: str
    document_names: list[str]
    team_member_name: str = "a team member"


@dataclass
class InvitationEmailData:
    """Invitation details needed to render Submit invitation emails."""

    invitation_id: int
    email: str
    token: str
    role_name: Optional[str]
    project_name: str
    proponent_name: str


class SubmitRepository:
    """Direct Submit DB access without importing sibling app internals."""

    def __init__(self, session):
        self.session = session
        self.metadata = MetaData()
        self._tables = {}

    def _table(self, table_name: str) -> Table:
        if table_name not in self._tables:
            self._tables[table_name] = Table(
                table_name,
                self.metadata,
                autoload_with=self.session.get_bind(),
            )
        return self._tables[table_name]

    @staticmethod
    def _full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
        return " ".join(part for part in [first_name, last_name] if part).strip()

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

    def find_pending_emails(self, limit=100) -> list[SubmitEmailQueueEntry]:
        email_queue = self._table("email_queue")
        stmt = (
            select(
                email_queue.c.id,
                email_queue.c.entity_id,
                email_queue.c.template_name,
            )
            .where(email_queue.c.status == constants.EMAIL_STATUS_PENDING)
            .limit(limit)
        )
        rows = self.session.execute(stmt).mappings().all()
        return [
            SubmitEmailQueueEntry(
                id=row["id"],
                entity_id=row["entity_id"],
                template_name=row["template_name"],
            )
            for row in rows
        ]

    def mark_email_sent(self, email_id: int):
        email_queue = self._table("email_queue")
        stmt = (
            update(email_queue)
            .where(email_queue.c.id == email_id)
            .values(
                status=constants.EMAIL_STATUS_SENT,
                error_message=None,
                sent_at=datetime.utcnow(),
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def mark_email_failed(self, email_id: int, error_message: str):
        email_queue = self._table("email_queue")
        stmt = (
            update(email_queue)
            .where(email_queue.c.id == email_id)
            .values(
                status=constants.EMAIL_STATUS_FAILED,
                error_message=(error_message or "")[:500],
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def rollback(self):
        """Reset the current transaction before recording a failed job."""
        self.session.rollback()

    def get_package_email_data(self, package_id: int) -> Optional[PackageEmailData]:
        packages = self._table("packages")
        package_types = self._table("package_types")
        account_projects = self._table("account_projects")
        projects = self._table("projects")
        proponents = self._table("proponents")
        users = self._table("users")
        account_users = self._table("account_users")

        stmt = (
            select(
                packages.c.id.label("package_id"),
                packages.c.account_project_id,
                packages.c.name.label("package_name"),
                packages.c.submitted_on,
                package_types.c.name.label("package_type"),
                projects.c.name.label("project_name"),
                proponents.c.name.label("proponent_name"),
                account_users.c.first_name.label("submitter_first_name"),
                account_users.c.last_name.label("submitter_last_name"),
                account_users.c.work_email_address.label("submitter_email"),
            )
            .select_from(
                packages.join(package_types, packages.c.type_id == package_types.c.id)
                .join(
                    account_projects,
                    packages.c.account_project_id == account_projects.c.id,
                )
                .join(projects, account_projects.c.project_id == projects.c.id)
                .outerjoin(proponents, projects.c.proponent_id == proponents.c.id)
                .outerjoin(users, packages.c.submitted_by == users.c.auth_guid)
                .outerjoin(account_users, account_users.c.user_id == users.c.id)
            )
            .where(packages.c.id == package_id)
        )
        row = self.session.execute(stmt).mappings().first()
        if not row:
            return None

        return PackageEmailData(
            package_id=row["package_id"],
            account_project_id=row["account_project_id"],
            package_name=row["package_name"],
            package_type=row["package_type"],
            submitted_on=row["submitted_on"],
            submitter_name=self._full_name(
                row["submitter_first_name"],
                row["submitter_last_name"],
            ),
            submitter_email=row["submitter_email"] or "",
            project_name=row["project_name"] or "",
            proponent_name=row["proponent_name"] or "",
            document_names=self.get_package_document_names(package_id),
        )

    def get_awaiting_manager_email_data(self, package_id: int) -> Optional[PackageEmailData]:
        data = self.get_package_email_data(package_id)
        if data:
            data.team_member_name = self.get_reviewer_name_for_awaiting_manager_package(package_id)
        return data

    def get_package_document_names(self, package_id: int) -> list[str]:
        items = self._table("items")
        submissions = self._table("submissions")
        submitted_documents = self._table("submitted_documents")

        stmt = (
            select(submitted_documents.c.name)
            .select_from(
                items.join(submissions, submissions.c.item_id == items.c.id)
                .join(
                    submitted_documents,
                    submitted_documents.c.id == submissions.c.submitted_document_id,
                )
            )
            .where(
                items.c.package_id == package_id,
                submissions.c.type == constants.SUBMISSION_TYPE_DOCUMENT,
                submissions.c.active.is_(True),
                submissions.c.deleted.is_(False),
            )
            .order_by(items.c.sort_order, submissions.c.created_date)
        )
        return [row[0] for row in self.session.execute(stmt).all()]

    def get_reviewer_name_for_awaiting_manager_package(self, package_id: int) -> str:
        items = self._table("items")
        reviews = self._table("submission_reviews")
        review_entries = self._table("submission_review_entries")
        users = self._table("users")
        staff_users = self._table("staff_users")

        awaiting_statuses = [
            constants.ITEM_STATUS_MP_AWAITING_MANAGER_APPROVAL,
            constants.ITEM_STATUS_CC_AWAITING_MANAGER_APPROVAL,
        ]
        stmt = (
            select(
                review_entries.c.updated_by,
                staff_users.c.first_name,
                staff_users.c.last_name,
            )
            .select_from(
                items.join(
                    reviews,
                    (reviews.c.item_id == items.c.id) & (reviews.c.active.is_(True)),
                )
                .join(
                    review_entries,
                    (review_entries.c.review_id == reviews.c.id)
                    & (
                        review_entries.c.type
                        == constants.SUBMISSION_REVIEW_ENTRY_STAFF_RECOMMENDATION
                    ),
                )
                .outerjoin(users, users.c.auth_guid == review_entries.c.updated_by)
                .outerjoin(staff_users, staff_users.c.user_id == users.c.id)
            )
            .where(
                items.c.package_id == package_id,
                items.c.status.in_(awaiting_statuses),
                review_entries.c.updated_by.is_not(None),
            )
            .order_by(items.c.sort_order)
            .limit(1)
        )
        row = self.session.execute(stmt).mappings().first()
        if not row:
            return "a team member"
        staff_name = self._full_name(row["first_name"], row["last_name"])
        return staff_name or row["updated_by"] or "a team member"

    def get_project_admin_emails(self, account_project_id: int) -> list[str]:
        account_users = self._table("account_users")
        user_roles = self._table("user_roles")
        roles = self._table("roles")

        admin_roles = [
            constants.ROLE_PROJECT_ADMIN,
            constants.ROLE_ACCOUNT_PRIMARY_ADMIN,
        ]
        stmt = (
            select(account_users.c.work_email_address)
            .select_from(
                account_users.join(
                    user_roles,
                    account_users.c.id == user_roles.c.account_user_id,
                )
                .join(roles, user_roles.c.role_id == roles.c.id)
            )
            .where(
                user_roles.c.account_project_id == account_project_id,
                user_roles.c.active.is_(True),
                roles.c.role_name.in_(admin_roles),
            )
        )
        return [
            row[0]
            for row in self.session.execute(stmt).all()
            if row[0]
        ]

    def get_invitation_email_data(self, invitation_id: int) -> Optional[InvitationEmailData]:
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
