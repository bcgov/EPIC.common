"""Tests for the work phase-sync cron trigger (runs after EXTRACT_WORK)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
for _path in (PROJECT_ROOT, SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from epic_cron.models.external import submit_v2, track_work  # noqa: E402
from epic_cron.services.work_phase_sync_service import (  # noqa: E402
    WorkPhaseSyncError,
    WorkPhaseSyncService,
)
from tasks.work_phase_sync import WorkPhaseSync  # noqa: E402

SERVICE = "epic_cron.services.work_phase_sync_service"


def _app(base_url="http://submit"):
    """Return a Flask app, optionally configured with a Submit API base URL."""
    app = Flask(__name__)
    if base_url:
        app.config["SUBMIT_API_BASE_URL"] = base_url
    return app


def _response(payload):
    """Return a mock requests response yielding the given JSON payload."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _counts(archived=0, created=0, skipped=False):
    """Return the payload the Submit endpoint answers with."""
    return {"work_id": 1, "archived": archived, "created": created, "skipped": skipped}


def _run(post, work_ids):
    """Run the sync with the Submit call and the work lookup patched."""
    with patch(f"{SERVICE}.SubmitApiService._get_headers", return_value={"Authorization": "Bearer tok"}), \
            patch.object(WorkPhaseSyncService, "_get_work_ids", return_value=work_ids), \
            patch(f"{SERVICE}.session_scope"), \
            patch(f"{SERVICE}.requests.post", side_effect=post) as mock_post:
        return WorkPhaseSyncService.sync_work_phases(session_factory=object()), mock_post


def test_skips_when_submit_api_not_configured():
    """Without SUBMIT_API_BASE_URL the job is a no-op."""
    with _app(base_url=None).app_context():
        summary = WorkPhaseSyncService.sync_work_phases(session_factory=object())
    assert summary == {"works": 0, "archived": 0, "created": 0, "skipped": 0, "failed": 0}


def test_calls_endpoint_per_work_and_aggregates_counts():
    """Every work is reconciled and the counts are added up."""
    with _app().app_context():
        summary, post = _run([_response(_counts(archived=2, created=1)), _response(_counts(archived=1))], [11, 12])

    assert [call.args[0] for call in post.call_args_list] == [
        "http://submit/api/works/11/phase-sync", "http://submit/api/works/12/phase-sync"]
    assert summary == {"works": 2, "archived": 3, "created": 1, "skipped": 0, "failed": 0}


def test_counts_skipped_works():
    """A work whose lock was held by another run is counted as skipped."""
    with _app().app_context():
        summary, _ = _run([_response(_counts(skipped=True))], [11])

    assert summary["skipped"] == 1 and summary["works"] == 1


def test_failing_work_does_not_stop_the_others_but_fails_the_job():
    """All works are attempted, then the job raises so it exits non-zero."""
    with _app().app_context():
        with pytest.raises(WorkPhaseSyncError):
            _run([requests.RequestException("boom"), _response(_counts(archived=1))], [11, 12])


def test_failed_work_is_completed_by_the_next_run():
    """The run after a failure reconciles the work that failed."""
    with _app().app_context():
        with pytest.raises(WorkPhaseSyncError):
            _run([requests.RequestException("boom")], [11])

        summary, post = _run([_response(_counts(archived=1, created=1))], [11])

    assert post.call_count == 1
    assert summary["archived"] == 1 and summary["created"] == 1 and summary["failed"] == 0


def test_http_error_response_counts_as_failure():
    """A 500 from Submit (a step failed there) is a failure to retry."""
    failing = MagicMock()
    failing.raise_for_status.side_effect = requests.HTTPError("500")
    with _app().app_context():
        with pytest.raises(WorkPhaseSyncError):
            _run([failing], [11])


def test_request_uses_the_configured_timeout():
    """Each call is bounded by a timeout so one hung call cannot block the run."""
    app = _app()
    app.config["CONNECT_TIMEOUT"] = "7"
    with app.app_context(), patch(f"{SERVICE}.requests.post", return_value=_response(_counts())) as post:
        WorkPhaseSyncService._sync_single_work("http://submit", {}, 5)

    assert post.call_args.kwargs["timeout"] == 7


def test_get_work_ids_returns_distinct_active_non_deleted_works():
    """Only works with an active association that are not deleted are reconciled, each once."""
    engine = create_engine("sqlite://")
    track_work.Base.metadata.create_all(engine)
    submit_v2.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for work_id, is_deleted in ((1, False), (2, False), (3, True), (4, False)):
        session.add(track_work.TrackWork(id=work_id, project_id=1, is_deleted=is_deleted))
    session.add_all([
        submit_v2.SubmitAccountProjectWorkV2(id=1, account_project_id=1, work_id=1, is_active=True),
        submit_v2.SubmitAccountProjectWorkV2(id=2, account_project_id=2, work_id=1, is_active=True),
        submit_v2.SubmitAccountProjectWorkV2(id=3, account_project_id=1, work_id=2, is_active=False),
        submit_v2.SubmitAccountProjectWorkV2(id=4, account_project_id=1, work_id=3, is_active=True),
    ])
    session.commit()

    assert WorkPhaseSyncService._get_work_ids(session) == [1]


class TestExtractThenSync:
    """The phase sync runs even when the work extraction fails, and failures are not hidden."""

    def test_runs_both_stages_in_order(self):
        """With no errors the extraction runs, then the phase sync."""
        calls = []
        with _app().app_context(), patch.object(WorkPhaseSync, "run", side_effect=lambda: calls.append("sync")):
            WorkPhaseSync.extract_then_sync(lambda: calls.append("extract"))

        assert calls == ["extract", "sync"]

    def test_phase_sync_still_runs_when_extraction_fails(self):
        """A failed extraction does not stop the sync, and its error is raised afterwards."""
        extract = MagicMock(side_effect=RuntimeError("track down"))
        with _app().app_context(), patch.object(WorkPhaseSync, "run") as sync:
            with pytest.raises(RuntimeError, match="track down"):
                WorkPhaseSync.extract_then_sync(extract)

        sync.assert_called_once()

    def test_phase_sync_failure_is_raised(self):
        """A failed sync after a good extraction makes the job fail."""
        extract = MagicMock()
        with _app().app_context(), patch.object(WorkPhaseSync, "run", side_effect=WorkPhaseSyncError("sync")):
            with pytest.raises(WorkPhaseSyncError):
                WorkPhaseSync.extract_then_sync(extract)

        extract.assert_called_once()
