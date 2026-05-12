"""Local Submit models used by epic-cron sync jobs."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SubmitProject(Base):
    """Minimal Submit project mapping for sync jobs."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    epic_guid = Column(String, nullable=True)
    proponent_id = Column(Integer, nullable=True)
    ea_certificate = Column(String, nullable=True)
    has_approved_condition = Column(Boolean, default=False, nullable=False)


class SubmitProponent(Base):
    """Minimal Submit proponent mapping for sync jobs."""

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
