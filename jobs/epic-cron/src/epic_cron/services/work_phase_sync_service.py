# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Trigger the package reconcile in Submit for every work that has an onboarded account project.

When a work moves to a new phase, Submit archives the work's packages from the previous phase and
creates the mandatory packages of the new phase. That logic lives in submit-api; this job only selects
the works and calls the submit-api endpoint for each one.

The job keeps no state of its own. Submit derives everything from the stored work phase and package
statuses, and the call is idempotent. Each run therefore repeats the call for every work, so a run that
failed part way, or a package that only finished after the phase moved, is completed by the next run.
"""
import requests
from flask import current_app

from epic_cron.models.db import session_scope
from epic_cron.models.external.submit_v2 import SubmitAccountProjectWorkV2
from epic_cron.models.external.track_work import TrackWork
from epic_cron.services.submit_api_service import SubmitApiService

_DEFAULT_TIMEOUT = 60


class WorkPhaseSyncError(RuntimeError):
    """Raised after every work was attempted when at least one work failed, so the job exits non-zero."""


class WorkPhaseSyncService:
    """Service to trigger the work phase reconcile in Submit per work."""

    @staticmethod
    def sync_work_phases(session_factory):
        """Call the Submit phase-sync endpoint for each work with an active account project association.

        A failure for one work is logged and does not stop the others. If any work failed, the error is
        raised once all works were attempted. Returns a summary of the counts returned by Submit.
        """
        summary = {"works": 0, "archived": 0, "created": 0, "skipped": 0, "failed": 0}

        submit_api_base_url = current_app.config.get("SUBMIT_API_BASE_URL")
        if not submit_api_base_url:
            current_app.logger.warning("SUBMIT_API_BASE_URL not configured. Skipping work phase sync.")
            return summary

        headers = SubmitApiService._get_headers()  # pylint: disable=protected-access

        with session_scope(session_factory) as session:
            work_ids = WorkPhaseSyncService._get_work_ids(session)
        current_app.logger.info("Found %d works to reconcile.", len(work_ids))

        for work_id in work_ids:
            try:
                counts = WorkPhaseSyncService._sync_single_work(submit_api_base_url, headers, work_id)
            except requests.RequestException as err:
                summary["failed"] += 1
                current_app.logger.error("Work phase sync failed for work %s: %s", work_id, err)
                continue
            summary["works"] += 1
            summary["archived"] += counts.get("archived", 0)
            summary["created"] += counts.get("created", 0)
            summary["skipped"] += 1 if counts.get("skipped") else 0

        current_app.logger.info(
            "Work phase sync complete. works=%d archived=%d created=%d skipped=%d failed=%d",
            summary["works"], summary["archived"], summary["created"], summary["skipped"], summary["failed"],
        )
        if summary["failed"]:
            raise WorkPhaseSyncError(
                f"Work phase sync failed for {summary['failed']} work(s); they are retried on the next run."
            )
        return summary

    @staticmethod
    def _get_work_ids(session):
        """Return the ids of non-deleted works that have an active account project association."""
        rows = (
            session.query(SubmitAccountProjectWorkV2.work_id)
            .join(TrackWork, TrackWork.id == SubmitAccountProjectWorkV2.work_id)
            .filter(SubmitAccountProjectWorkV2.is_active.is_(True), TrackWork.is_deleted.is_(False))
            .distinct()
            .order_by(SubmitAccountProjectWorkV2.work_id)
            .all()
        )
        return [row[0] for row in rows]

    @staticmethod
    def _sync_single_work(base_url, headers, work_id):
        """Call the Submit phase-sync endpoint for one work and return its summary."""
        endpoint = f"{base_url}/api/works/{work_id}/phase-sync"
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", _DEFAULT_TIMEOUT))
        current_app.logger.info("Reconciling packages for work %s: %s", work_id, endpoint)

        response = requests.post(endpoint, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json() or {}
