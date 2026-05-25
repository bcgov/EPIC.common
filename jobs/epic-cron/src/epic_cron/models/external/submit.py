"""Default local Submit models used by epic-cron sync jobs.

These aliases keep existing imports working for v2-only Submit sync code.
"""

from epic_cron.models.external.submit_v2 import Base
from epic_cron.models.external.submit_v2 import SubmitProjectV2 as SubmitProject
from epic_cron.models.external.submit_v2 import SubmitProponentV2 as SubmitProponent


__all__ = ["Base", "SubmitProject", "SubmitProponent"]
