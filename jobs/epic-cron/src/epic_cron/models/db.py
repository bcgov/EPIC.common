from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import current_app

# DB initialization for SQLAlchemy
db = SQLAlchemy()

def create_session(engine_uri):
    """Create a sessionmaker for the given database engine URI."""
    engine = create_engine(engine_uri)
    return sessionmaker(bind=engine)

def init_db(app):
    """Initialize the session for the Epic Track database."""
    print("Initializing Epic Track database...")
    return create_session(app.config['TRACK_DATABASE_URI'])

def init_compliance_db(app):
    """Initialize the session for the Compliance database."""
    print("Initializing Compliance database...")
    return create_session(app.config['COMPLIANCE_DATABASE_URI'])

def init_submit_db(app):
    """Initialize the session for the Submit database."""
    print("Initializing Submit database...")
    return create_session(app.config['SUBMIT_DATABASE_URI'])
