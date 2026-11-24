"""Local Submit v2 models used by epic-cron sync jobs."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class SubmitProjectV2(Base):
    """Submit v2 project mapping.

    Submit v2 stores proponents in a separate proponents table.
    """

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    epic_guid = Column(String, nullable=True)
    proponent_id = Column(Integer, nullable=True)
    ea_certificate = Column(String, nullable=True)
    has_approved_condition = Column(Boolean, default=False, nullable=False)


class SubmitAccountProjectV2(Base):
    """Submit v2 account project mapping (account_projects table).

    Links an account to a project; used to determine which projects have been
    onboarded by an account and therefore require report syncing.
    """

    __tablename__ = "account_projects"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, nullable=False)
    project_id = Column(Integer, nullable=False)


class SubmitAccountProjectWorkV2(Base):
    """Submit v2 account project work mapping (account_project_works table).

    Links an onboarded account project to an EPIC.track work; used to find the works whose
    packages must be reconciled with the work's current phase.
    """

    __tablename__ = "account_project_works"

    id = Column(Integer, primary_key=True)
    account_project_id = Column(Integer, nullable=False)
    work_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class SubmitProjectReportV2(Base):
    """Submit v2 project report mapping (project_reports table).

    Flat table holding one row per approved report phase synced from the
    condition repository.
    """

    __tablename__ = "project_reports"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False)
    report_id = Column(Integer, nullable=False)
    condition_number = Column(Integer, nullable=True)
    condition_subsection = Column(String, nullable=True)
    report_type = Column(String, nullable=True)
    report_sub_type = Column(String, nullable=True)
    report_name = Column(String, nullable=True)
    phase = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    timing = Column(String, nullable=True)
    management_plan = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_date = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )


class SubmitProponentV2(Base):
    """Submit v2 proponent mapping."""

    __tablename__ = "proponents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String(50), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    updated_date = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )


# Submit v2 user type values (users.type) stored as an enum column.
USER_TYPE_PROPONENT = "PROPONENT"
USER_TYPE_STAFF = "STAFF"

# Submit v2 user status ids (user_status.id) referenced by users.status_id.
USER_STATUS_ACTIVE = 1
USER_STATUS_INACTIVE = 2
USER_STATUS_ACCESS_REVOKED = 3


class SubmitUserV2(Base):
    """Submit v2 user mapping (users table).

    Only the columns required by inactivity deactivation are mapped here.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    auth_guid = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status_id = Column(Integer, nullable=False, default=USER_STATUS_ACTIVE)


class SubmitAccountUserV2(Base):
    """Submit v2 account user mapping (account_users table).

    Holds the ``last_login_at`` timestamp used to detect proponent inactivity.
    """

    __tablename__ = "account_users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
