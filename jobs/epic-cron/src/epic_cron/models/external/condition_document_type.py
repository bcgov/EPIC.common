"""Condition Document Type Model - Local copy for epic-cron."""

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class DocumentType(Base):
    """Definition of the Condition document_types entity."""

    __tablename__ = 'document_types'
    __table_args__ = {'schema': 'condition'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_type = Column(String(255), nullable=False)
