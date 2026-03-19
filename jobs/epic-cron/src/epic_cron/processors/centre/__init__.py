# processors/centre/__init__.py
from typing import Callable, Dict

from epic_cron.data_classes.email_details import EmailDetails

from ...models.email_job import EmailJob
from .access_denied import process_access_denied
from .access_granted import process_access_granted
from .access_request_received_dst import process_access_request_received_dst
from .access_request_submitted import process_access_request_submitted
from .ssl_digest_notification import process_ssl_digest_notification


# Template names (export as constants, so they’re used consistently)
TEMPLATE_ACCESS_REQUEST_SUBMITTED = "access_request_submitted_confirmation.html"
ACCESS_REQUEST_RECEIVED_NOTIFICATION = 'access_request_received_notification.html'
ACCESS_GRANTED_NOTIFICATION = "access_granted_notification.html"
ACCESS_DENIED_NOTIFICATION = "access_denied_notification.html"
SSL_DIGEST_NOTIFICATION = "ssl_digest_notification.html"

# Map: template_name -> processor function
# Each processor takes (job: EmailJob) and returns EmailDetails
PROCESSORS: Dict[str, Callable[[EmailJob], EmailDetails]] = {
    TEMPLATE_ACCESS_REQUEST_SUBMITTED: process_access_request_submitted,
    ACCESS_REQUEST_RECEIVED_NOTIFICATION: process_access_request_received_dst,
    ACCESS_GRANTED_NOTIFICATION: process_access_granted,
    ACCESS_DENIED_NOTIFICATION: process_access_denied,
    SSL_DIGEST_NOTIFICATION: process_ssl_digest_notification,
}

__all__ = [
    "TEMPLATE_ACCESS_REQUEST_SUBMITTED",
    "SSL_DIGEST_NOTIFICATION",
    "PROCESSORS",
    "process_access_request_submitted",
    "process_access_request_received_dst",
]
