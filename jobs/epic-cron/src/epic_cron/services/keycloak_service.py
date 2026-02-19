# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Keycloak admin functions – same pattern as submit-api KeycloakService."""
import requests
from flask import current_app


# Same group path as submit-api (SUBMIT / EAO_MANAGER)
EAO_MANAGER_GROUP_PATH = "SUBMIT/EAO_MANAGER"


class KeycloakService:
    """Keycloak admin API – same token and request pattern as submit-api."""

    @staticmethod
    def _get_admin_token():
        """Create an admin token (same as submit-api KeycloakService._get_admin_token)."""
        config = current_app.config
        base_url = config.get("KEYCLOAK_BASE_URL")
        realm = config.get("KEYCLOAK_REALM_NAME")
        admin_client_id = config.get("KEYCLOAK_EMAILER_CLIENT")
        admin_secret = config.get("KEYCLOAK_EMAILER_SECRET")
        timeout = int(config.get("CONNECT_TIMEOUT", 60))
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"

        if not admin_client_id or not admin_secret:
            raise ValueError(
                "KEYCLOAK_EMAILER_CLIENT and KEYCLOAK_EMAILER_SECRET must be set in .env"
            )

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        # Use dict so requests form-encodes correctly (handles special chars in secret)
        data = {
            "client_id": admin_client_id,
            "grant_type": "client_credentials",
            "client_secret": admin_secret,
        }
        response = requests.post(
            token_url,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("access_token")

    @staticmethod
    def _request_keycloak(relative_url: str):
        """GET request to Keycloak admin API (same URL pattern as submit-api)."""
        base_url = current_app.config.get("KEYCLOAK_BASE_URL")
        realm = current_app.config.get("KEYCLOAK_REALM_NAME")
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", 60))
        admin_token = KeycloakService._get_admin_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}",
        }
        url = f"{base_url}/auth/admin/realms/{realm}/{relative_url}"
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    @staticmethod
    def get_groups(brief_representation: bool = False):
        """Get all top-level groups."""
        response = KeycloakService._request_keycloak(
            f"groups?briefRepresentation={brief_representation}"
        )
        return response.json()

    @staticmethod
    def get_sub_groups(group_id: str):
        """Return the subgroups of given group."""
        response = KeycloakService._request_keycloak(f"groups/{group_id}/children")
        return response.json()

    @staticmethod
    def get_group_id_by_path(group_path: str) -> str:
        """Find a Keycloak group by full path (e.g. 'SUBMIT/EAO_MANAGER') and return its ID."""
        segments = group_path.strip("/").split("/")
        current_groups = KeycloakService.get_groups(brief_representation=True)
        current_group = None

        for segment in segments:
            matched = next((g for g in current_groups if g["name"] == segment), None)
            if not matched:
                raise ValueError(f"Group segment '{segment}' not found.")
            current_group = matched
            current_groups = KeycloakService.get_sub_groups(current_group["id"])

        return current_group["id"]

    @staticmethod
    def get_members_for_group(group_id: str):
        """Get the members of a group (Keycloak user objects with email, etc.)."""
        response = KeycloakService._request_keycloak(f"groups/{group_id}/members")
        return response.json()

    @classmethod
    def get_eao_manager_emails(cls) -> list:
        """Return email addresses of SUBMIT/EAO_MANAGER group members (same as submit-api flow)."""
        try:
            group_id = cls.get_group_id_by_path(EAO_MANAGER_GROUP_PATH)
            members = cls.get_members_for_group(group_id)
            return [m.get("email") for m in members if m.get("email")]
        except (ValueError, requests.RequestException):
            return []