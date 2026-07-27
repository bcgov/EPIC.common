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
"""Service for interacting with the Submit API."""
import requests
from flask import current_app


class SubmitApiService:
    """Service to interact with Submit API using service account authentication."""

    @staticmethod
    def _get_service_account_token():
        """Get access token using service account credentials."""
        config = current_app.config
        base_url = config.get("KEYCLOAK_BASE_URL")
        realm = config.get("KEYCLOAK_REALM_NAME")
        client_id = config.get("SERVICE_ACCOUNT_ID")
        client_secret = config.get("SERVICE_ACCOUNT_SECRET")
        timeout = int(config.get("CONNECT_TIMEOUT", 60))
        
        if not client_id or not client_secret:
            raise ValueError("SERVICE_ACCOUNT_ID and SERVICE_ACCOUNT_SECRET must be configured")
        
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": client_id,
            "grant_type": "client_credentials",
            "client_secret": client_secret,
        }
        
        try:
            response = requests.post(token_url, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json().get("access_token")
        except Exception as e:
            current_app.logger.error(f"Failed to get service account token: {e}")
            raise

    @staticmethod
    def _get_headers():
        """Get headers with authorization token for Submit API requests."""
        token = SubmitApiService._get_service_account_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    @staticmethod
    def get_staff_user_works():
        """
        Fetch all staff user works from Submit API.
        
        Returns:
            List of staff user work dictionaries
        """
        submit_api_url = current_app.config.get("SUBMIT_API_BASE_URL")
        if not submit_api_url:
            raise ValueError("SUBMIT_API_BASE_URL not configured")
        
        url = f"{submit_api_url}/api/staff-user-works"
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", 60))
        headers = SubmitApiService._get_headers()
        
        try:
            current_app.logger.info(f"Fetching staff user works from {url}")
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            staff_user_works = response.json()
            current_app.logger.info(f"Fetched {len(staff_user_works)} staff user works from Submit API")
            return staff_user_works
        except Exception as e:
            current_app.logger.error(f"Failed to fetch staff user works: {e}")
            raise

    @staticmethod
    def create_or_update_staff_user_work(email: str, work_id: int, role: str):
        """
        Create or update a staff user work via Submit API.
        
        Args:
            email: Email address of the staff user
            work_id: Work ID from EPIC.track
            role: Work role (TEAM_LEAD or TEAM_MEMBER)
        
        Returns:
            Response data from the API
        """
        submit_api_url = current_app.config.get("SUBMIT_API_BASE_URL")
        if not submit_api_url:
            raise ValueError("SUBMIT_API_BASE_URL not configured")
        
        url = f"{submit_api_url}/api/staff-user-works"
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", 60))
        headers = SubmitApiService._get_headers()
        
        payload = {
            "email": email,
            "work_id": work_id,
            "role": role
        }
        
        try:
            current_app.logger.debug(f"Creating/updating staff user work: {payload}")
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            current_app.logger.info(f"Successfully created/updated staff user work: email={email}, work_id={work_id}, role={role}")
            return response.json()
        except Exception as e:
            current_app.logger.error(f"Failed to create/update staff user work: {e}")
            raise

    @staticmethod
    def delete_staff_user_work(work_id: int):
        """
        Delete (deactivate) a staff user work via Submit API.
        
        Args:
            work_id: Work ID from EPIC.track
        
        Returns:
            Response data from the API
        """
        submit_api_url = current_app.config.get("SUBMIT_API_BASE_URL")
        if not submit_api_url:
            raise ValueError("SUBMIT_API_BASE_URL not configured")
        
        url = f"{submit_api_url}/api/staff-user-works/work/{work_id}"
        timeout = int(current_app.config.get("CONNECT_TIMEOUT", 60))
        headers = SubmitApiService._get_headers()
        
        try:
            current_app.logger.debug(f"Deleting staff user work: work_id={work_id}")
            response = requests.delete(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            current_app.logger.info(f"Successfully deleted staff user work: work_id={work_id}")
            return response.json()
        except Exception as e:
            current_app.logger.error(f"Failed to delete staff user work: {e}")
            raise
