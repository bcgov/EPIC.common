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

EMAIL_STATUS_PENDING = 'PENDING'
EMAIL_STATUS_SENT = 'SENT'
EMAIL_STATUS_FAILED = 'FAILED'

MANAGEMENT_PLAN_SUBMISSION_CONFIRMATION_EMAIL_TEMPLATE = 'management_plan_submission_verification.html'
MANAGEMENT_PLAN_UPDATE_REQUEST_CREATED_EMAIL_TEMPLATE = 'management_plan_update_request_created.html'
NEW_USER_INVITATION_EMAIL_TEMPLATE = 'new_user_invitation.html'
MANAGEMENT_PLAN_SUBMISSION_NOTIFY_STAFF_EMAIL_TEMPLATE = 'management_plan_submission_notify_staff.html'
SUBMISSION_AWAITING_MANAGER_APPROVAL_EMAIL_TEMPLATE = 'submission_awaiting_manager_approval.html'
MANAGEMENT_PLAN_RESUBMISSION_REQUEST_EMAIL_TEMPLATE = 'resubmission_request.html'

ROLE_ACCOUNT_PRIMARY_ADMIN = 'ACCOUNT_PRIMARY_ADMIN'
ROLE_PROJECT_ADMIN = 'PROJECT_ADMIN'
ROLE_SPECIFIC_SUBMISSION_CONTRIBUTOR = 'SPECIFIC_SUBMISSION_CONTRIBUTOR'

PROPONENT_STATUS_ELIGIBLE = 'ELIGIBLE'
PROPONENT_STATUS_INELIGIBLE = 'INELIGIBLE'

SUBMISSION_TYPE_DOCUMENT = 'DOCUMENT'

ITEM_STATUS_CC_AWAITING_MANAGER_APPROVAL = 'CC_AWAITING_MANAGER_APPROVAL'
ITEM_STATUS_MP_AWAITING_MANAGER_APPROVAL = 'MP_AWAITING_MANAGER_APPROVAL'

SUBMISSION_REVIEW_ENTRY_STAFF_RECOMMENDATION = 'STAFF_RECOMMENDATION'
