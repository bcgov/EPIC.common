import requests
from flask import current_app
from sqlalchemy import MetaData, Table, select

from epic_cron.models.db import init_db


class TrackService:
    """Service to interact with the Track API."""

    @staticmethod
    def fetch_track_data():
        """Fetch and log data from the track.projects table, joining with proponents."""
        print("Fetching data from track database...")
        required_fields = ["id", "name", "epic_guid", "proponent_name", "proponent_id", "ea_certificate"]

        track_session = init_db(current_app)
        with track_session() as session:

            track_metadata = MetaData()
            track_projects_table = Table('projects', track_metadata, autoload_with=session.bind)
            track_proponents_table = Table('proponents', track_metadata, autoload_with=session.bind)

            print(f"Selecting required fields: {required_fields} and joining with proponents...")
            # Join projects with proponents to get proponent name
            query = (
                select(
                    *[track_projects_table.c[field] for field in required_fields if field != "proponent_name"],
                    track_proponents_table.c.name.label("proponent_name")
                )
                .join(track_proponents_table, track_projects_table.c.proponent_id == track_proponents_table.c.id)
            )
            track_data = session.execute(query).fetchall()
            print(f"Number of rows fetched from track.projects: {len(track_data)}")

            debug_logs_enabled = current_app.config.get("ENABLE_DETAILED_LOGS", False)
            if debug_logs_enabled:
                for row in track_data:
                    print(f"Fetched row: {dict(row._mapping)}")

        return track_data

    @staticmethod
    def fetch_projects():
        """
        Not in use.
        Fetch project data from the Track API and map the required fields.

        Args:
            required_fields (list): List of fields required in the response.

        Returns:
            List of project dictionaries with only the required fields.
        """
        # Get the Track API base URL and endpoint
        track_api_base_url = current_app.config.get("TRACK_API_BASE_URL")
        track_projects_endpoint = f"{track_api_base_url}/api/v1/projects?return_type=LIST_TYPE&with_works=false"

        # Fetch the Bearer token
        token = TrackService._get_admin_token()
        if not token:
            raise Exception("Failed to fetch authorization token.")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        print(f"Fetching projects from Track API: {track_projects_endpoint}")
        try:
            # Make the GET request to the Track API with Authorization
            response = requests.get(track_projects_endpoint, headers=headers, timeout=30)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

            # Parse the JSON response
            projects = response.json()
            print(f"Track API returned {len(projects)} projects.")

            # Map the required fields
            mapped_projects = []
            for project in projects:
                mapped_project = {
                    "id": project.get("id"),
                    "name": project.get("name"),
                    "epic_guid": project.get("epic_guid"),
                    "proponent_name": project.get("proponent", {}).get("name"),
                    "proponent_id": project.get("proponent_id"),
                    "ea_certificate": project.get("ea_certificate", ""),
                }
                mapped_projects.append(mapped_project)

            print(f"Mapped {len(mapped_projects)} projects with required fields.")
            return mapped_projects

        except requests.RequestException as e:
            print(f"Error while calling Track API: {e}")
            raise

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
        admin_client_id = config.get("KEYCLOAK_SERVICE_ACCOUNT_ID")
        admin_secret = config.get("KEYCLOAK_SERVICE_ACCOUNT_SECRET")
        timeout = config.get("CONNECT_TIMEOUT", 60)

        # Construct token URL and headers
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Request body for client credentials grant
        data = f"client_id={admin_client_id}&grant_type=client_credentials&client_secret={admin_secret}"

        try:
            print(f"Fetching Keycloak token from: {token_url}")
            response = requests.post(token_url, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

            # Parse and return the access token
            access_token = response.json().get("access_token")
            if not access_token:
                raise Exception("Keycloak response did not include an access token.")
            return access_token

        except requests.RequestException as e:
            print(f"Error while fetching Keycloak token: {e}")
            raise
