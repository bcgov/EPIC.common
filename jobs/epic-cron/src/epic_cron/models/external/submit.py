"""Default local Submit models used by epic-cron sync jobs.

These aliases keep existing imports working for v2-only Submit sync code.
"""

from epic_cron.models.external.submit_v2 import (
    USER_STATUS_ACCESS_REVOKED,
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
    USER_TYPE_PROPONENT,
    USER_TYPE_STAFF,
    Base,
)
from epic_cron.models.external.submit_v2 import SubmitAccountUserV2 as SubmitAccountUser
from epic_cron.models.external.submit_v2 import SubmitProjectV2 as SubmitProject
from epic_cron.models.external.submit_v2 import SubmitProponentV2 as SubmitProponent
from epic_cron.models.external.submit_v2 import SubmitUserV2 as SubmitUser


__all__ = [
    "Base",
    "SubmitProject",
    "SubmitProponent",
    "SubmitUser",
    "SubmitAccountUser",
    "USER_TYPE_PROPONENT",
    "USER_TYPE_STAFF",
    "USER_STATUS_ACTIVE",
    "USER_STATUS_INACTIVE",
    "USER_STATUS_ACCESS_REVOKED",
]
