"""Helpers for Submit schema version-specific cron behavior."""

from epic_cron.models.external.submit_v1 import SubmitProjectV1
from epic_cron.models.external.submit_v2 import SubmitProjectV2, SubmitProponentV2


SUBMIT_SCHEMA_V1 = "v1"
SUBMIT_SCHEMA_V2 = "v2"


def get_submit_project_model(schema_version=SUBMIT_SCHEMA_V1):
    """Return the Submit project model for the requested schema version."""
    if schema_version == SUBMIT_SCHEMA_V1:
        return SubmitProjectV1
    return SubmitProjectV2


def get_submit_proponent_model(schema_version=SUBMIT_SCHEMA_V1):
    """Return the Submit proponent model for v2."""
    if schema_version != SUBMIT_SCHEMA_V2:
        raise ValueError("Submit v1 does not have a proponents table")
    return SubmitProponentV2


def build_submit_project_values(project_dict, schema_version=SUBMIT_SCHEMA_V1):
    """Build Submit project values for the requested schema version."""
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
