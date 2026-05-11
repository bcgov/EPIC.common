"""Initializations for db and marshmallow."""

from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Kept for older shell-context integrations that still import epic_cron.models.db.
# Cron database access should use explicit session factories instead.
db = SQLAlchemy()

# Marshmallow for database model schema
ma = Marshmallow()


def create_session(engine_uri):
    """Create a sessionmaker for the given database engine URI."""
    engine = create_engine(
        engine_uri,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    return sessionmaker(bind=engine)


def init_track_db(app):
    """Initialize the session for the Track database."""
    print("Initializing Track database...")
    return create_session(app.config['TRACK_DATABASE_URI'])


def init_compliance_db(app):
    """Initialize the session for the Compliance database."""
    print("Initializing Compliance database...")
    return create_session(app.config['COMPLIANCE_DATABASE_URI'])


def init_centre_db(app):
    """Initialize the session for the Centre database."""
    print("Initializing Centre database...")
    return create_session(app.config['CENTRE_DATABASE_URI'])


def init_condition_db(app):
    """Initialize the session for the Condition database."""
    print("Initializing Condition database...")
    return create_session(app.config['CONDITION_DATABASE_URI'])


def init_submit_db(app):
    """Initialize the session for the Submit database."""
    print("Initializing Submit database...")
    return create_session(app.config['SUBMIT_DATABASE_URI'])


# Aliases for backward compatibility
def init_db(app):
    """Initialize the session for the Track database (alias for init_track_db)."""
    return init_track_db(app)


def init_conditions_db(app):
    """Initialize the session for the Conditions database (alias for init_condition_db)."""
    return init_condition_db(app)
