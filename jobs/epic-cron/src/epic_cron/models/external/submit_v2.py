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
