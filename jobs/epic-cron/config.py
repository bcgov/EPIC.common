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
"""All of the configuration for the service is captured here.

All items are loaded,
or have Constants defined here that are loaded into the Flask configuration.
All modules and lookups get their configuration from the Flask config,
rather than reading environment variables directly or by accessing this configuration directly.
"""

import os
import sys

from dotenv import find_dotenv, load_dotenv


# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'config.DevConfig',
    'testing': 'config.TestConfig',
    'production': 'config.ProdConfig',
    'default': 'config.ProdConfig',
    # Alembic connects to migration config which is MET Analytics Database
    'migration': 'config.MigrationConfig',
}

def get_named_config(config_name: str = 'development'):
    """Return the configuration object based on the name.

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ['production', 'staging', 'default']:
        config = ProdConfig()
    elif config_name == 'testing':
        config = TestConfig()
    elif config_name == 'development':
        config = DevConfig()
    elif config_name == 'docker':
        config = DockerConfig()
    else:
        raise KeyError("Unknown configuration '{config_name}'")
    return config


class _Config():  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations."""

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = 'a secret'

    TESTING = False
    DEBUG = False

    # POSTGRESQL
    TRACK_DB_USER = os.getenv('TRACK_DATABASE_USERNAME', '')
    TRACK_DB_PASSWORD = os.getenv('TRACK_DATABASE_PASSWORD', '')
    TRACK_DB_NAME = os.getenv('TRACK_DATABASE_NAME', '')
    TRACK_DB_HOST = os.getenv('TRACK_DATABASE_HOST', '')
    TRACK_DB_PORT = os.getenv('TRACK_DATABASE_PORT', '5432')
    TRACK_DATABASE_URI = f'postgresql://{TRACK_DB_USER}:{TRACK_DB_PASSWORD}@{TRACK_DB_HOST}:{int(TRACK_DB_PORT)}/{TRACK_DB_NAME}'
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Compliance DB Configuration
    COMPLIANCE_DB_USER = os.getenv("COMPLIANCE_DATABASE_USERNAME", "")
    COMPLIANCE_DB_PASSWORD = os.getenv("COMPLIANCE_DATABASE_PASSWORD", "")
    COMPLIANCE_DB_NAME = os.getenv("COMPLIANCE_DATABASE_NAME", "")
    COMPLIANCE_DB_HOST = os.getenv("COMPLIANCE_DATABASE_HOST", "")
    COMPLIANCE_DB_PORT = os.getenv("COMPLIANCE_DATABASE_PORT", "5432")
    COMPLIANCE_DATABASE_URI = (
        f"postgresql://{COMPLIANCE_DB_USER}:{COMPLIANCE_DB_PASSWORD}@{COMPLIANCE_DB_HOST}:{int(COMPLIANCE_DB_PORT)}/{COMPLIANCE_DB_NAME}"
    )

    # SUBMIT DB Configuration
    SUBMIT_DB_USER = os.getenv("SUBMIT_DATABASE_USERNAME", "")
    SUBMIT_DB_PASSWORD = os.getenv("SUBMIT_DATABASE_PASSWORD", "")
    SUBMIT_DB_NAME = os.getenv("SUBMIT_DATABASE_NAME", "")
    SUBMIT_DB_HOST = os.getenv("SUBMIT_DATABASE_HOST", "")
    SUBMIT_DB_PORT = os.getenv("SUBMIT_DATABASE_PORT", "5432")
    SUBMIT_DATABASE_URI = (
        f"postgresql://{SUBMIT_DB_USER}:{SUBMIT_DB_PASSWORD}@{SUBMIT_DB_HOST}:{int(SUBMIT_DB_PORT)}/{SUBMIT_DB_NAME}"
    )

    # CONDITION DB Configuration
    CONDITION_DB_USER = os.getenv("CONDITION_DATABASE_USERNAME", "")
    CONDITION_DB_PASSWORD = os.getenv("CONDITION_DATABASE_PASSWORD", "")
    CONDITION_DB_NAME = os.getenv("CONDITION_DATABASE_NAME", "")
    CONDITION_DB_HOST = os.getenv("CONDITION_DATABASE_HOST", "")
    CONDITION_DB_PORT = os.getenv("CONDITION_DATABASE_PORT", "5432")
    CONDITION_DATABASE_URI = (
        f"postgresql://{CONDITION_DB_USER}:{CONDITION_DB_PASSWORD}@{CONDITION_DB_HOST}:{int(CONDITION_DB_PORT)}/{CONDITION_DB_NAME}"
    )

    # Debug logging for detailed logs in Project Extractor
    ENABLE_DETAILED_LOGS = os.getenv("ENABLE_DETAILED_LOGS", "false").lower() == "true"

    TRACK_API_BASE_URL=os.getenv('TRACK_API_BASE_URL')
    CONDITION_API_BASE_URL = os.getenv("CONDITION_API_BASE_URL")
    KEYCLOAK_BASE_URL = os.getenv('KEYCLOAK_BASE_URL')
    KEYCLOAK_REALM_NAME = os.getenv('KEYCLOAK_REALM_NAME', 'eao-epic')
    SERVICE_ACCOUNT_ID = os.getenv('SERVICE_ACCOUNT_ID')
    SERVICE_ACCOUNT_SECRET = os.getenv('SERVICE_ACCOUNT_SECRET')
    CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', 60))
    # TODO separate out clients for APIs and user management.
    # TODO API client wont need user management roles in keycloak.

    CLAMAV_HOST = os.getenv('CLAMAV_HOST')
    CLAMAV_PORT = os.getenv('CLAMAV_PORT')

    # CHES Configuration for Email Service
    CHES_TOKEN_ENDPOINT = os.getenv('CHES_TOKEN_ENDPOINT')
    CHES_CLIENT_ID = os.getenv('CHES_CLIENT_ID')
    CHES_CLIENT_SECRET = os.getenv('CHES_CLIENT_SECRET')
    CHES_BASE_URL = os.getenv('CHES_BASE_URL')
    
    # Submit Web Configuration
    WEB_URL = os.getenv('WEB_URL')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    STAFF_SUPPORT_MAIL_ID = os.getenv('STAFF_SUPPORT_MAIL_ID', '')
    SIGNUP_URL_PATH = os.getenv('SIGNUP_URL_PATH', '/proponent/registration')
    
    # Condition API Configuration
    CONDITION_API_BASE_URL = os.getenv('CONDITION_API_BASE_URL')
    
    # JWT_OIDC Settings for Submit
    JWT_OIDC_WELL_KNOWN_CONFIG = os.getenv('JWT_OIDC_WELL_KNOWN_CONFIG')
    JWT_OIDC_ALGORITHMS = os.getenv('JWT_OIDC_ALGORITHMS', 'RS256')
    JWT_OIDC_JWKS_URI = os.getenv('JWT_OIDC_JWKS_URI')
    JWT_OIDC_ISSUER = os.getenv('JWT_OIDC_ISSUER')
    JWT_OIDC_AUDIENCE = os.getenv('JWT_OIDC_AUDIENCE', 'account')
    JWT_OIDC_CACHING_ENABLED = os.getenv('JWT_OIDC_CACHING_ENABLED', 'True')
    JWT_OIDC_JWKS_CACHE_TIMEOUT = 300
    
    # Centre DB Configuration (for centre emailer)
    CENTRE_DB_USER = os.getenv("CENTRE_DATABASE_USERNAME", "")
    CENTRE_DB_PASSWORD = os.getenv("CENTRE_DATABASE_PASSWORD", "")
    CENTRE_DB_NAME = os.getenv("CENTRE_DATABASE_NAME", "")
    CENTRE_DB_HOST = os.getenv("CENTRE_DATABASE_HOST", "")
    CENTRE_DB_PORT = os.getenv("CENTRE_DATABASE_PORT", "5432")
    CENTRE_DATABASE_URI = (
        f"postgresql://{CENTRE_DB_USER}:{CENTRE_DB_PASSWORD}@{CENTRE_DB_HOST}:{int(CENTRE_DB_PORT)}/{CENTRE_DB_NAME}"
    )
    
    # For backward compatibility with submit_cron code
    SQLALCHEMY_DATABASE_URI = SUBMIT_DATABASE_URI
    
    ENVIRONMENT = os.getenv('ENVIRONMENT', os.getenv('ENV_NAME', ''))

class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    """Dev Config."""

    TESTING = False
    DEBUG = True
    print(f'SQLAlchemy URL (DevConfig): {_Config.TRACK_DATABASE_URI}')


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only.used by the py.test suite."""

    DEBUG = True
    TESTING = True
    DEBUG = True
    TESTING = True

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_TEST_USERNAME', 'postgres')
    DB_PASSWORD = os.getenv('DATABASE_TEST_PASSWORD', 'postgres')
    DB_NAME = os.getenv('DATABASE_TEST_NAME', 'testdb')
    DB_HOST = os.getenv('DATABASE_TEST_HOST', 'localhost')
    DB_PORT = os.getenv('DATABASE_TEST_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'

    JWT_OIDC_TEST_MODE = True
    # JWT_OIDC_ISSUER = _get_config('JWT_OIDC_TEST_ISSUER')
    JWT_OIDC_TEST_AUDIENCE = os.getenv('JWT_OIDC_TEST_AUDIENCE')
    JWT_OIDC_TEST_CLIENT_SECRET = os.getenv('JWT_OIDC_TEST_CLIENT_SECRET')
    JWT_OIDC_TEST_ISSUER = os.getenv('JWT_OIDC_TEST_ISSUER')
    JWT_OIDC_WELL_KNOWN_CONFIG = os.getenv('JWT_OIDC_WELL_KNOWN_CONFIG')
    JWT_OIDC_TEST_ALGORITHMS = os.getenv('JWT_OIDC_TEST_ALGORITHMS')
    JWT_OIDC_TEST_JWKS_URI = os.getenv('JWT_OIDC_TEST_JWKS_URI', default=None)
    JWT_OIDC_TEST_MODE = True

    JWT_OIDC_TEST_KEYS = {
        'keys': [
            {
                'kid': 'epictrack',
                'kty': 'RSA',
                'alg': 'RS256',
                'use': 'sig',
                'n': 'AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-'
                     'TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR',
                'e': 'AQAB'
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_JWKS = {
        'keys': [
            {
                'kid': 'forms-flow-ai',
                'kty': 'RSA',
                'alg': 'RS256',
                'use': 'sig',
                'n': 'AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-'
                     'TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR',
                'e': 'AQAB',
                'd': 'C0G3QGI6OQ6tvbCNYGCqq043YI_8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhskURaDwk4-'
                     '8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh_'
                     'xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0',
                'p': 'APXcusFMQNHjh6KVD_hOUIw87lvK13WkDEeeuqAydai9Ig9JKEAAfV94W6Aftka7tGgE7ulg1vo3eJoLWJ1zvKM',
                'q': 'AOjX3OnPJnk0ZFUQBwhduCweRi37I6DAdLTnhDvcPTrrNWuKPg9uGwHjzFCJgKd8KBaDQ0X1rZTZLTqi3peT43s',
                'dp': 'AN9kBoA5o6_Rl9zeqdsIdWFmv4DB5lEqlEnC7HlAP-3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhc',
                'dq': 'ANtbSY6njfpPploQsF9sU26U0s7MsuLljM1E8uml8bVJE1mNsiu9MgpUvg39jEu9BtM2tDD7Y51AAIEmIQex1nM',
                'qi': 'XLE5O360x-MhsdFXx8Vwz4304-MJg-oGSJXCK_ZWYOB_FGXFRTfebxCsSYi0YwJo-oNu96bvZCuMplzRI1liZw'
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_PEM = """-----BEGIN RSA PRIVATE KEY-----
    MIICXQIBAAKBgQDfn1nKQshOSj8xw44oC2klFWSNLmK3BnHONCJ1bZfq0EQ5gIfg
    tlvB+Px8Ya+VS3OnK7Cdi4iU1fxO9ktN6c6TjmmmFevk8wIwqLthmCSF3r+3+h4e
    ddj7hucMsXWv05QUrCPoL6YUUz7Cgpz7ra24rpAmK5z7lsV+f3BEvXkrUQIDAQAB
    AoGAC0G3QGI6OQ6tvbCNYGCqq043YI/8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhs
    kURaDwk4+8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh/
    xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0CQQD13LrBTEDR44ei
    lQ/4TlCMPO5bytd1pAxHnrqgMnWovSIPSShAAH1feFugH7ZGu7RoBO7pYNb6N3ia
    C1idc7yjAkEA6Nfc6c8meTRkVRAHCF24LB5GLfsjoMB0tOeEO9w9Ous1a4o+D24b
    AePMUImAp3woFoNDRfWtlNktOqLel5PjewJBAN9kBoA5o6/Rl9zeqdsIdWFmv4DB
    5lEqlEnC7HlAP+3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhcCQQDb
    W0mOp436T6ZaELBfbFNulNLOzLLi5YzNRPLppfG1SRNZjbIrvTIKVL4N/YxLvQbT
    NrQw+2OdQACBJiEHsdZzAkBcsTk7frTH4yGx0VfHxXDPjfTj4wmD6gZIlcIr9lZg
    4H8UZcVFN95vEKxJiLRjAmj6g273pu9kK4ymXNEjWWJn
    -----END RSA PRIVATE KEY-----"""


class DockerConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only.used by the py.test suite."""

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_DOCKER_USERNAME')
    DB_PASSWORD = os.getenv('DATABASE_DOCKER_PASSWORD')
    DB_NAME = os.getenv('DATABASE_DOCKER_NAME')
    DB_HOST = os.getenv('DATABASE_DOCKER_HOST')
    DB_PORT = os.getenv('DATABASE_DOCKER_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'

    print(f'SQLAlchemy URL (Docker): {SQLALCHEMY_DATABASE_URI}')


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production Config."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False