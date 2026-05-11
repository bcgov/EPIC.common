"""Data shapes used to render Submit emails."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
