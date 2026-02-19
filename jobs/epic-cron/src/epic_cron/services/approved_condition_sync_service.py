import requests
from flask import current_app
from submit_api.models.project import Project

from epic_cron.models import db


class ApprovedConditionService:
    """Service to interact with the Condition API."""

    @staticmethod
    def sync_projects_with_approved_conditions():
        """
        Fetch project data from the Condition API

        """
        # Get the Condition API base URL and endpoint
        condition_api_base_url = current_app.config.get("CONDITION_API_BASE_URL")
        approved_projects_endpoint = f"{condition_api_base_url}/api/projects/with-approved-conditions"

        # Fetch the Bearer token
        token = ApprovedConditionService._get_admin_token()

        if not token:
            raise Exception("Failed to fetch authorization token.")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        current_app.logger.info(f"Fetching projects from Condition API: {approved_projects_endpoint}")
        try:
            # Make the GET request to the Condition API with Authorization
            response = requests.get(approved_projects_endpoint, headers=headers, timeout=30)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            projects = response.json()

            current_app.logger.info(f"Condition API returned {len(projects)} projects.")

            epic_guids = [p.get("epic_guid") for p in projects if p.get("epic_guid")]

            updated_count = 0

            for epic_guid in epic_guids:
                # Fetch the Project by epic_guid
                project = db.session.query(Project).filter_by(epic_guid=epic_guid).first()
                if project:
                    if not project.has_approved_condition:
                        project.has_approved_condition = True
                        updated_count += 1

            db.session.commit()

            current_app.logger.info(f"Updated {updated_count} projects with has_approved_condition=True.")
            return {"updated_projects": updated_count}

        except requests.RequestException as e:
            db.session.rollback()
            current_app.logger.error(f"Error while calling Condition API: {e}")
            raise
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error: {e}")
            raise
        finally:
            db.session.remove()

    @staticmethod
    def _get_admin_token():
        """
        Fetch an admin token using client credentials from Keycloak.

        Returns:
            str: Access token string.
        """
        # Get Keycloak configuration from Flask app config
        config = current_app.config
        base_url = config.get("KEYCLOAK_BASE_URL")
        realm = config.get("KEYCLOAK_REALM_NAME")
        admin_client_id = config.get("SERVICE_ACCOUNT_ID")
        admin_secret = config.get("SERVICE_ACCOUNT_SECRET")
        timeout = config.get("CONNECT_TIMEOUT", 60)

        # Construct token URL and headers
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Request body for client credentials grant
        data = f"client_id={admin_client_id}&grant_type=client_credentials&client_secret={admin_secret}"

        try:
            current_app.logger.info(f"Fetching Keycloak token from: {token_url}")
            response = requests.post(token_url, data=data, headers=headers, timeout=timeout)

            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

            # Parse and return the access token
            access_token = response.json().get("access_token")
            if not access_token:
                raise Exception("Keycloak response did not include an access token.")
            return access_token

        except requests.RequestException as e:
            current_app.logger.error(f"Error while fetching Keycloak token: {e}")
            raise
