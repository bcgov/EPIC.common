"""Minimal Submit table mappings used by epic-cron.

These classes intentionally model only the columns this cron job reads or writes.
They keep epic-cron independent from Submit's Flask app, dependency pins, and
model graph.
"""

import enum

from sqlalchemy import Boolean, Column, Enum as SqlEnum, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SubmitProponentStatus(str, enum.Enum):
    """Known Submit proponent status values."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INVITE_GENERATED = "INVITE_GENERATED"
    PENDING_ONBOARDING = "PENDING_ONBOARDING"
    ONBOARDED = "ONBOARDED"


class SubmitProject(Base):
    """Submit projects table fields used by sync and condition jobs."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    proponent_id = Column(Integer, nullable=False)
    ea_certificate = Column(String(255), nullable=True)
    epic_guid = Column(String(255), nullable=True)
    has_approved_condition = Column(Boolean, nullable=True, default=False)


class SubmitProponent(Base):
    """Submit proponents table fields used by sync and eligibility jobs."""

    __tablename__ = "proponents"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String, nullable=False)
    status = Column(
        SqlEnum(
            SubmitProponentStatus,
            name="proponentstatus",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=True,
    )
    is_deleted = Column(Boolean, nullable=False, default=False)
