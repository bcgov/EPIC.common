import requests
from flask import current_app
from submit_api.models.project import Project as SubmitProjectModel

class ApprovedConditionService:
    """Service to interact with the Condition API."""

    @staticmethod
    def sync_approved_conditions(session):
        """
        Fetch project data from the Condition API and update local DB.
        Also updates Proponent status to ELIGIBLE.
        """
        # Get the Condition API base URL and endpoint
        condition_api_base_url = current_app.config.get("CONDITION_API_BASE_URL")
        # Ensure URL is available
        if not condition_api_base_url:
            print("WARNING: CONDITION_API_BASE_URL not configured. Skipping Condition API sync.")
            return

        approved_projects_endpoint = f"{condition_api_base_url}/api/projects/with-approved-conditions"
        
        token = ApprovedConditionService._get_admin_token()

        if not token:
            print("Failed to fetch authorization token for Condition API.")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        print(f"Fetching projects from Condition API: {approved_projects_endpoint}")
        try:
            # Make the GET request to the Condition API with Authorization
            response = requests.get(approved_projects_endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            projects_data = response.json()

            print(f"Condition API returned {len(projects_data)} projects.")
            
            epic_guids = [p.get("epic_guid") for p in projects_data if p.get("epic_guid")]
            
            if not epic_guids:
                return

            # Update Projects
            print(f"Updating projects matching {len(epic_guids)} GUIDs...")
            projects_to_update = session.query(SubmitProjectModel).filter(
                SubmitProjectModel.epic_guid.in_(epic_guids)
            ).all()

            proponent_ids_to_update = set()
            updated_count = 0

            for project in projects_to_update:
                if not project.has_approved_condition:
                    project.has_approved_condition = True
                    updated_count += 1
                
                # Collect proponent IDs for status update.. if atleast one of the project has approved condition , propoent is elible for onboarding
                if project.proponent_id:
                    proponent_ids_to_update.add(project.proponent_id)
            
            print(f"Updated has_approved_condition for {updated_count} projects.")

            # Update Proponents - REMOVED
            # The service now returns the list of proponent IDs to be updated by a separate task
            
            session.commit()
            print(f"Successfully synced approved conditions. Returning {len(proponent_ids_to_update)} proponent IDs.")
            
            return proponent_ids_to_update

        except requests.RequestException as e:
            print(f"Error while calling Condition API: {e}")
            return set()
        except Exception as e:
            session.rollback()
            print(f"Unexpected error calling Condition API: {e}")
            raise e

    @staticmethod
    def _get_admin_token():
        """
        Fetch an admin token using client credentials from Keycloak.
        """
        # Get Keycloak configuration from Flask app config
        config = current_app.config
        base_url = config.get("KEYCLOAK_BASE_URL")
        realm = config.get("KEYCLOAK_REALM_NAME")
        admin_client_id = config.get("SERVICE_ACCOUNT_ID")
        admin_secret = config.get("SERVICE_ACCOUNT_SECRET")
        timeout = config.get("CONNECT_TIMEOUT", 60)
        
        if not base_url or not admin_client_id:
            print("Keycloak configuration missing.")
            return None

        # Construct token URL and headers
        token_url = f"{base_url}/auth/realms/{realm}/protocol/openid-connect/token"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Request body for client credentials grant
        data = f"client_id={admin_client_id}&grant_type=client_credentials&client_secret={admin_secret}"

        try:
            # print(f"Fetching Keycloak token from: {token_url}")
            response = requests.post(token_url, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()

            # Parse and return the access token
            access_token = response.json().get("access_token")
            return access_token

        except requests.RequestException as e:
            print(f"Error while fetching Keycloak token: {e}")
            return None
