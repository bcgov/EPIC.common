"""Data class for email details."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EmailDetails:  # pylint: disable=too-many-instance-attributes
    """Email details class."""

    sender: str
    recipients: List[str]
    subject: str
    body: Optional[str] = None
    body_type: str = "text"
    template_name: Optional[str] = None
    body_args: Optional[dict] = None
    cc: Optional[List[str]] = None  # pylint: disable=invalid-name
    bcc: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize optional fields."""
        self.body_args = self.body_args or {}
        self.cc = self.cc or []  # pylint: disable=invalid-name
        self.bcc = self.bcc or []
        if not self.sender:
            raise ValueError("sender is required")
        if not self.recipients:
            raise ValueError("at least one recipient is required")
        if not self.body and not self.template_name:
            raise ValueError("either body or template_name is required")
