"""Submit package email repository."""

from typing import Optional

from sqlalchemy import select

from epic_cron.data_classes.submit_email import PackageEmailData
from epic_cron.repositories.submit_base import SubmitTableRepository
from epic_cron.utils import submit_constants


class SubmitPackageRepository(SubmitTableRepository):
    """Read the Submit data needed to render package-related emails."""

    @staticmethod
    def _full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
        return " ".join(part for part in [first_name, last_name] if part).strip()

    def get_email_data(self, package_id: int) -> Optional[PackageEmailData]:
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
            document_names=self.get_document_names(package_id),
        )

    def get_awaiting_manager_email_data(self, package_id: int) -> Optional[PackageEmailData]:
        data = self.get_email_data(package_id)
        if data:
            data.team_member_name = self.get_reviewer_name_for_awaiting_manager_package(package_id)
        return data

    def get_document_names(self, package_id: int) -> list[str]:
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
                submissions.c.type == submit_constants.SUBMISSION_TYPE_DOCUMENT,
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
            submit_constants.ITEM_STATUS_MP_AWAITING_MANAGER_APPROVAL,
            submit_constants.ITEM_STATUS_CC_AWAITING_MANAGER_APPROVAL,
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
                        == submit_constants.SUBMISSION_REVIEW_ENTRY_STAFF_RECOMMENDATION
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
            submit_constants.ROLE_PROJECT_ADMIN,
            submit_constants.ROLE_ACCOUNT_PRIMARY_ADMIN,
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
        return [row[0] for row in self.session.execute(stmt).all() if row[0]]
