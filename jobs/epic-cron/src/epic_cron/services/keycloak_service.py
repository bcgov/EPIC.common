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
from typing import Optional
from urllib.parse import quote

import requests
from flask import current_app


# Same group path as submit-api (SUBMIT / EAO_MANAGER)
EAO_MANAGER_GROUP_PATH = "SUBMIT/EAO_MANAGER"


class KeycloakService:
    """Keycloak admin API – same token and request pattern as submit-api."""

    @staticmethod
    def _get_admin_token():
        """Create an admin token using service account credentials."""
        config = current_app.config
        base_url = config.get("KEYCLOAK_BASE_URL")
        realm = config.get("KEYCLOAK_REALM_NAME")
        admin_client_id = config.get("SERVICE_ACCOUNT_ID")
        admin_secret = config.get("SERVICE_ACCOUNT_SECRET")
        timeout = int(config.get("CONNECT_TIMEOUT", 60))
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"

        if not admin_client_id or not admin_secret:
            raise ValueError(
                "SERVICE_ACCOUNT_ID and SERVICE_ACCOUNT_SECRET must be set in .env"
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
    def _request_keycloak_optional(relative_url: str) -> Optional[requests.Response]:
        """GET request to Keycloak admin API; returns None on 404."""
        base_url = current_app.config.get("KEYCLOAK_BASE_URL")
        realm = current_app.config.get("KEYCLOAK_REALM_NAME")
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", 60))
        try:
            admin_token = KeycloakService._get_admin_token()
        except (ValueError, requests.RequestException):
            return None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}",
        }
        url = f"{base_url}/auth/admin/realms/{realm}/{relative_url}"
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response
        except requests.RequestException:
            return None

    @staticmethod
    def _normalize_user(keycloak_user: dict) -> dict:
        """Map Keycloak user (firstName, lastName, username) to common shape."""
        return {
            "first_name": (keycloak_user.get("firstName") or "").strip(),
            "last_name": (keycloak_user.get("lastName") or "").strip(),
            "username": (keycloak_user.get("username") or "").strip(),
        }

    @classmethod
    def get_user_by_guid(cls, user_auth_guid: str) -> Optional[dict]:
        """
        Get user from Keycloak by guid.

        In the DB, user_auth_guid is the Keycloak user id (UUID). Try GET users/{id} first;
        if 404, try username search (e.g. xxxxx@idir). Returns dict with first_name, last_name, username; or None.
        """
        if not (user_auth_guid or user_auth_guid.strip()):
            return None
        guid = user_auth_guid.strip()
        response = cls._request_keycloak_optional(f"users/{guid}")
        if response:
            return cls._normalize_user(response.json())
        quoted = quote(guid, safe="")
        response = cls._request_keycloak_optional(
            f"users?exact=true&username={quoted}"
        )
        if response:
            users = response.json()
            if users and len(users) > 0:
                return cls._normalize_user(users[0])
        return None

    @staticmethod
    def format_user_display_name(user: dict, fallback_id: str, include_username: bool = False) -> str:
        """
        Build display name from user dict.
        If include_username is True: "First Last (username@idir)". Otherwise: "First Last" only.
        """
        first = (user.get("first_name") or "").strip()
        last = (user.get("last_name") or "").strip()
        username = (user.get("username") or "").strip()
        name_part = f"{first} {last}".strip()
        if name_part and username and include_username:
            return f"{name_part} ({username})"
        if name_part:
            return name_part
        if username:
            return username
        return fallback_id

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