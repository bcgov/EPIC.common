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
"""This module contains constants used in the application."""

SUBMISSION_PACKAGE_TYPE_EMAIL_SENDER_MAP = {
    'Management Plan': 'EAO.ManagementPlanSupport@gov.bc.ca',
    'IEM': 'EAO.ManagementPlanSupport@gov.bc.ca'
}

SUBMISSION_PACKAGE_TYPE_SENDER_MAP = {
    'Management Plan': 'The Management Plan Team at the Environmental Assessment Office',
    'IEM': 'EAO.ManagementPlanSupport@gov.bc.ca'
}

PACKAGE_ENTITY_TYPE = 'PACKAGE'
INVITATION_ENTITY_TYPE = 'INVITATION'
