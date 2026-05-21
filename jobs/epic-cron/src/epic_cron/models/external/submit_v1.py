"""Local Submit v1 models used by epic-cron sync jobs."""

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class SubmitProjectV1(Base):
    """Submit v1 project mapping.

    Submit v1 stores proponent details directly on the projects table.
    """

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    proponent_id = Column(Integer, nullable=False)
    proponent_name = Column(String, nullable=False)
    ea_certificate = Column(String, nullable=True)
    epic_guid = Column(String, nullable=True)
    has_approved_condition = Column(Boolean, default=False, nullable=True)
