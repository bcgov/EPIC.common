"""Minimal Submit table mappings used by epic-cron.

These classes intentionally model only the columns this cron job reads or writes.
They keep epic-cron independent from Submit's Flask app, dependency pins, and
model graph.
"""

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


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
    status = Column(String(50), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
