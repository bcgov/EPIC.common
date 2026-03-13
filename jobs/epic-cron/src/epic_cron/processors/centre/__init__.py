# processors/centre/__init__.py
from typing import Callable, Dict

from epic_cron.data_classes.email_details import EmailDetails

from ...models.email_job import EmailJob
from .access_denied import process_access_denied
from .access_granted import process_access_granted
from .access_request_received_dst import process_access_request_received_dst
from .access_request_submitted import process_access_request_submitted


# Template names (export as constants, so they’re used consistently)
TEMPLATE_ACCESS_REQUEST_SUBMITTED = "access_request_submitted_confirmation.html"
ACCESS_REQUEST_RECEIVED_NOTIFICATION = 'access_request_received_notification.html'
ACCESS_GRANTED_NOTIFICATION = "access_granted_notification.html"
ACCESS_DENIED_NOTIFICATION = "access_denied_notification.html"

# Map: template_name -> processor function
# Each processor takes (job: EmailJob) and returns EmailDetails
PROCESSORS: Dict[str, Callable[[EmailJob], EmailDetails]] = {
    TEMPLATE_ACCESS_REQUEST_SUBMITTED: process_access_request_submitted,
    ACCESS_REQUEST_RECEIVED_NOTIFICATION: process_access_request_received_dst,
    ACCESS_GRANTED_NOTIFICATION: process_access_granted,
    ACCESS_DENIED_NOTIFICATION: process_access_denied
}

__all__ = [
    "TEMPLATE_ACCESS_REQUEST_SUBMITTED",
    "PROCESSORS",
    "process_access_request_submitted",
    "process_access_request_received_dst",
]
