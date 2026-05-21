"""Tests for Submit schema version selection."""

from pathlib import Path

import pytest

from epic_cron.services.submit_schema_adapter import (
    DEFAULT_SUBMIT_SCHEMA_VERSION,
    build_submit_project_values,
    get_submit_project_model,
    get_submit_proponent_model,
    normalize_submit_schema_version,
)


def test_submit_schema_defaults_to_v1():
    """Default Submit schema version is prod-safe v1."""
    assert DEFAULT_SUBMIT_SCHEMA_VERSION == "v1"
    assert normalize_submit_schema_version() == "v1"
    assert normalize_submit_schema_version("") == "v1"


def test_submit_schema_normalizes_valid_values():
    """Schema version arguments are normalized before use."""
    assert normalize_submit_schema_version("V1") == "v1"
    assert normalize_submit_schema_version(" v2 ") == "v2"


def test_submit_schema_rejects_invalid_values():
    """Unsupported schema versions fail clearly."""
    with pytest.raises(ValueError, match="Submit schema version must be v1 or v2"):
        normalize_submit_schema_version("v3")


def test_project_values_include_proponent_name_only_for_v1():
    """Submit v1 writes proponent_name while Submit v2 does not."""
    project_dict = {
        "id": 1,
        "name": "Example Project",
        "epic_guid": "123",
        "proponent_id": 99,
        "proponent_name": "Example Holder",
        "ea_certificate": "EAC-001",
    }

    v1_values = build_submit_project_values(project_dict, "v1")
    v2_values = build_submit_project_values(project_dict, "v2")

    assert v1_values["proponent_name"] == "Example Holder"
    assert "proponent_name" not in v2_values


def test_schema_models_match_submit_shapes():
    """Schema-specific models expose only their supported tables/columns."""
    assert hasattr(get_submit_project_model("v1"), "proponent_name")
    assert not hasattr(get_submit_project_model("v2"), "proponent_name")

    with pytest.raises(ValueError, match="Submit v1 does not have a proponents table"):
        get_submit_proponent_model("v1")


def test_submit_cron_shell_defaults_to_v1():
    """The shell wrapper defaults to v1 but passes through an explicit argument."""
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "run_project_cron_submit.sh").read_text()

    assert 'SUBMIT_SCHEMA_VERSION="${1:-v1}"' in script
    assert 'python3 invoke_jobs.py SUBMIT "${SUBMIT_SCHEMA_VERSION}"' in script
