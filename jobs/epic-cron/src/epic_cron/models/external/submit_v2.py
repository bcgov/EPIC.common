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
