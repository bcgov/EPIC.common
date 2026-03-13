"""Service for integrating with the Common Hosted Email Service."""
import base64
import json
from datetime import datetime, timedelta

import requests
from flask import current_app
from submit_api.data_classes.email_details import EmailDetails

from submit_api.utils.template import Template

class ChesApiService:
    """CHES api Service class."""

    def __init__(self):
        """Initiate class."""
        self.token_endpoint = current_app.config.get('CHES_TOKEN_ENDPOINT')
        self.service_client_id = current_app.config.get('CHES_CLIENT_ID')
        self.service_client_secret = current_app.config.get('CHES_CLIENT_SECRET')
        self.ches_base_url = current_app.config.get('CHES_BASE_URL')
        current_app.logger.info(f'Initialized ChesApiService with CHES_BASE_URL: {self.ches_base_url}')
        self.access_token, self.token_expiry = self._get_access_token()

    def _get_access_token(self):
        """Retrieve access token from CHES."""
        basic_auth_encoded = base64.b64encode(
            bytes(f'{self.service_client_id}:{self.service_client_secret}', 'utf-8')
        ).decode('utf-8')
        data = 'grant_type=client_credentials'
        current_app.logger.info(f'Fetching access token from: {self.token_endpoint}')

        try:
            response = requests.post(
                self.token_endpoint,
                data=data,
                headers={
                    'Authorization': f'Basic {basic_auth_encoded}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                timeout=10
            )
            response.raise_for_status()

            response_json = response.json()

            expires_in = response_json['expires_in']
            expiry_time = datetime.now() + timedelta(seconds=expires_in)

            return response_json['access_token'], expiry_time
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Error occurred while fetching access token: {str(e)}')
            if e.response is not None:
                current_app.logger.error(f'Status Code: {e.response.status_code}')
                current_app.logger.error(f'Response Content: {e.response.text}')
            else:
                current_app.logger.error("No response received from server.")
            raise  # Re-raise the exception to propagate the error

    def _ensure_valid_token(self):
        if datetime.now() >= self.token_expiry:
            self.access_token, self.token_expiry = self._get_access_token()

    @staticmethod
    def _get_email_body_from_template(template_name: str, body_args: dict, template_sub_directory: str = None):
        """Get email body from a template with optional environment message for centre templates."""
        if not template_name:
            raise ValueError('Template name is required')

        full_template_path = f'{template_sub_directory}/{template_name}' if template_sub_directory else template_name
        template = Template.get_template(full_template_path)
        if not template:
            raise ValueError('Template not found')
        # logo is taken from submit UI / Web app..
        # Went for this approach since making it base64 is hard to get it working in gmail..
        # gmail strips the logo if base64 is used
        # this is like submit web hosts the logo and the email uses it as a static server to get the logo image.
        body_args['logo_url'] = f'{current_app.config.get("WEB_URL")}/assets/EAO_Logo-BZOR9oRj.png'
        rendered_body = template.render(body_args)

        # Add environment notification for centre templates in non-production
        if template_sub_directory == 'centre':
            env_name = current_app.config.get('ENVIRONMENT', '')
            if env_name and env_name.lower() != 'production':
                env_message = ChesApiService._create_environment_banner(env_name)
                rendered_body = ChesApiService._inject_environment_banner(rendered_body, env_message)

        return rendered_body

    @staticmethod
    def _create_environment_banner(env_name: str) -> str:
        """Create HTML banner showing the current environment."""
        return f'''
            <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 10px; 
                        margin: 20px 0; text-align: center; font-size: 14px; color: #856404;">
                <strong>You are using {env_name} environment</strong>
            </div>
        '''

    @staticmethod
    def _inject_environment_banner(rendered_body: str, env_message: str) -> str:
        """Inject environment banner into the email body."""
        if '</body>' in rendered_body:
            return rendered_body.replace('</body>', f'{env_message}</body>')
        else:
            return rendered_body + env_message

    def _get_email_body(self, email_details: EmailDetails, template_sub_directory: str = None):
        """Get email body based on details or template."""
        if email_details.body:
            body = email_details.body
            body_type = 'text'
        else:
            body = self._get_email_body_from_template(email_details.template_name,
                                                      email_details.body_args, template_sub_directory)
            body_type = 'html'

        return body, body_type

    def send_email(self, email_details: EmailDetails, template_sub_directory: str = None):
        """Generate document based on template and data."""
        self._ensure_valid_token()

        body, body_type = self._get_email_body(email_details, template_sub_directory)

        request_body = {
            'bodyType': body_type,
            'body': body,
            'subject': email_details.subject,
            'from': email_details.sender,
            'to': email_details.recipients,
            'cc': email_details.cc,
            'bcc': email_details.bcc,
        }
        json_request_body = json.dumps(request_body)


        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }

        url = f'{self.ches_base_url}/api/v1/email'

        try:
            response = requests.post(url, data=json_request_body, headers=headers, timeout=10)
            current_app.logger.info(f'Response status from CHES email endpoint: {response.status_code}')
            response.raise_for_status()

            response_json = response.json()
            return response_json, response.status_code
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Error occurred while sending email: {str(e)}')
            if e.response is not None:
                current_app.logger.error(f'Status Code: {e.response.status_code}')
                current_app.logger.error(f'Response Content: {e.response.text}')
            else:
                current_app.logger.error("No response received from server.")
            raise  # Re-raise the exception to propagate the error
