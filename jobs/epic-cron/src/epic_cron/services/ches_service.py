"""Service for integrating with the Common Hosted Email Service."""
import base64
import json
from datetime import datetime, timedelta

import requests
from flask import current_app
from epic_cron.data_classes.email_details import EmailDetails

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

    def _get_email_body(self, email_details: EmailDetails):
        """Get email body based on details or template."""
        if email_details.body:
            body = email_details.body
            body_type = email_details.body_type
        else:
            raise ValueError('Email body must be pre-rendered before sending')

        return body, body_type

    def send_email(self, email_details: EmailDetails):
        """Generate document based on template and data."""
        self._ensure_valid_token()

        body, body_type = self._get_email_body(email_details)

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
            current_app.logger.info(
                'Email sent via CHES | to=%s | subject=%s | from=%s | status=%s',
                ', '.join(email_details.recipients),
                email_details.subject,
                email_details.sender,
                response.status_code,
            )
            return response_json, response.status_code
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Error occurred while sending email: {str(e)}')
            if e.response is not None:
                current_app.logger.error(f'Status Code: {e.response.status_code}')
                current_app.logger.error(f'Response Content: {e.response.text}')
            else:
                current_app.logger.error("No response received from server.")
            raise  # Re-raise the exception to propagate the error
