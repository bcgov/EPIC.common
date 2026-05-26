"""Tests for EPIC Public document type mapping."""

import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from epic_cron.services.epic_public_service import EpicPublicService
from tasks.epic_public_extractor import EpicPublicExtractor


class DocumentTypeRow:
    """Simple row stand-in for condition.document_types query results."""

    def __init__(self, document_type_id, document_type):
        self.id = document_type_id
        self.document_type = document_type


def _app(config=None):
    app = Flask(__name__)
    app.config.update(config or {})
    return app


def test_document_type_map_uses_condition_document_type_names():
    """Config maps EPIC Public type IDs to stable Condition document type names."""
    app = _app({
        "EPIC_PUBLIC_DOCUMENT_TYPE_MAP": "type-a:Other Order, type-b:Certificate",
    })

    with app.app_context():
        assert EpicPublicService.get_document_type_name_map() == {
            "type-a": "Other Order",
            "type-b": "Certificate",
        }


def test_fetch_all_documents_uses_resolved_document_type_id():
    """Mapped documents receive the runtime-resolved Condition document type ID."""
    raw_docs = [{
        "_id": "doc-1",
        "displayName": "Certificate",
        "documentFileName": "certificate.pdf",
        "datePosted": "2025-01-01T00:00:00Z",
        "legislation": 2002,
        "project": {"_id": "project-1"},
    }]
    app = _app()

    with app.app_context(), patch.object(EpicPublicService, "_fetch_documents_by_type", return_value=raw_docs):
        documents = EpicPublicService.fetch_all_documents(
            document_type_id_map={"type-a": 4},
            default_document_type_id=1,
        )

    assert documents == [{
        "document_id": "doc-1",
        "document_label": "Certificate",
        "document_file_name": "certificate.pdf",
        "date_issued": "2025-01-01T00:00:00Z",
        "act": 2002,
        "project_id": "project-1",
        "document_type_id": 4,
    }]


def test_resolve_document_type_config_queries_condition_document_types():
    """The extractor resolves configured names to IDs before fetching EPIC Public data."""
    app = _app({
        "EPIC_PUBLIC_DOCUMENT_TYPE_MAP": "source-other:Other Order",
    })

    with app.app_context(), patch("tasks.epic_public_extractor.session_scope") as session_scope:
        session = session_scope.return_value.__enter__.return_value
        session.query.return_value.filter.return_value.all.return_value = [
            DocumentTypeRow(4, "Other Order"),
        ]

        document_type_id_map, default_document_type_id = EpicPublicExtractor._resolve_document_type_config(object())

    assert document_type_id_map == {"source-other": 4}
    assert default_document_type_id is None


def test_resolve_document_type_config_uses_default_when_map_is_empty():
    """An empty map resolves the default type for unfiltered EPIC Public fetches."""
    app = _app()

    with app.app_context(), patch("tasks.epic_public_extractor.session_scope") as session_scope:
        session = session_scope.return_value.__enter__.return_value
        session.query.return_value.filter.return_value.all.return_value = [
            DocumentTypeRow(1, "Certificate"),
        ]

        document_type_id_map, default_document_type_id = EpicPublicExtractor._resolve_document_type_config(object())

    assert document_type_id_map == {}
    assert default_document_type_id == 1


def test_resolve_document_type_config_skips_missing_condition_type():
    """Bad config skips only the source type that cannot resolve a target type."""
    app = _app({
        "EPIC_PUBLIC_DOCUMENT_TYPE_MAP": "source-cert:Certificate,source-other:Other Order",
    })

    with app.app_context(), \
            patch.object(app.logger, "error") as log_error, \
            patch("tasks.epic_public_extractor.session_scope") as session_scope:
        session = session_scope.return_value.__enter__.return_value
        session.query.return_value.filter.return_value.all.return_value = [
            DocumentTypeRow(1, "Certificate"),
        ]

        document_type_id_map, default_document_type_id = EpicPublicExtractor._resolve_document_type_config(object())

    assert document_type_id_map == {"source-cert": 1}
    assert default_document_type_id is None
    log_error.assert_called_once()


def test_fetch_all_documents_returns_empty_when_no_document_type_resolves():
    """Documents are not fetched when no target document type can be resolved."""
    app = _app()

    with app.app_context(), \
            patch.object(app.logger, "error") as log_error, \
            patch.object(EpicPublicService, "_fetch_documents_by_type") as fetch_documents:
        documents = EpicPublicService.fetch_all_documents(
            document_type_id_map={},
            default_document_type_id=None,
        )

    assert documents == []
    fetch_documents.assert_not_called()
    log_error.assert_called_once()
