"""Helpers for Submit schema version-specific cron behavior."""

from epic_cron.models.external.submit_v1 import SubmitProjectV1
from epic_cron.models.external.submit_v2 import SubmitProjectV2, SubmitProponentV2


DEFAULT_SUBMIT_SCHEMA_VERSION = "v1"
SUBMIT_SCHEMA_V1 = "v1"
SUBMIT_SCHEMA_V2 = "v2"
VALID_SUBMIT_SCHEMA_VERSIONS = {SUBMIT_SCHEMA_V1, SUBMIT_SCHEMA_V2}


def normalize_submit_schema_version(schema_version=None):
    """Return a supported Submit schema version, defaulting to v1."""
    if not schema_version:
        return DEFAULT_SUBMIT_SCHEMA_VERSION

    normalized = str(schema_version).strip().lower()
    if normalized not in VALID_SUBMIT_SCHEMA_VERSIONS:
        raise ValueError("Submit schema version must be v1 or v2")
    return normalized


def is_submit_schema_v1(schema_version=None):
    """Return whether the given schema version is Submit v1."""
    return normalize_submit_schema_version(schema_version) == SUBMIT_SCHEMA_V1


def is_submit_schema_v2(schema_version=None):
    """Return whether the given schema version is Submit v2."""
    return normalize_submit_schema_version(schema_version) == SUBMIT_SCHEMA_V2


def get_submit_project_model(schema_version=None):
    """Return the Submit project model for the requested schema version."""
    schema_version = normalize_submit_schema_version(schema_version)
    if schema_version == SUBMIT_SCHEMA_V1:
        return SubmitProjectV1
    return SubmitProjectV2


def get_submit_proponent_model(schema_version=None):
    """Return the Submit proponent model for v2."""
    schema_version = normalize_submit_schema_version(schema_version)
    if schema_version == SUBMIT_SCHEMA_V1:
        raise ValueError("Submit v1 does not have a proponents table")
    return SubmitProponentV2


def build_submit_project_values(project_dict, schema_version=None):
    """Build Submit project values for the requested schema version."""
    schema_version = normalize_submit_schema_version(schema_version)
    values = {
        "id": project_dict["id"],
        "name": project_dict["name"],
        "epic_guid": project_dict.get("epic_guid"),
        "proponent_id": project_dict.get("proponent_id"),
        "ea_certificate": project_dict.get("ea_certificate"),
    }

    if schema_version == SUBMIT_SCHEMA_V1:
        values["proponent_name"] = project_dict.get("proponent_name")

    return values
