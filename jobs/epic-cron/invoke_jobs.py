import os
import sys
import argparse
import logging
from datetime import datetime
from flask import Flask
from utils.logger import setup_logging
import config

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tasks.project_extractor import ProjectExtractor, TargetSystem  # Import the enum
from tasks.proponent_extractor import ProponentExtractor
from tasks.proponent_status_updater import ProponentStatusUpdater
from tasks.virus_scanner import VirusScanner
from tasks.submit_mail import SubmitMailer
from tasks.centre_mail import CentreMailer
from tasks.sync_approved_condition import SyncApprovedCondition
from tasks.work_extractor import WorkExtractor
from tasks.phase_extractor import PhaseExtractor

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first

logger = logging.getLogger(__name__)


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    from epic_cron.models.db import db  # Import db for Flask-SQLAlchemy

    app = Flask(__name__)
    logger.info(f'Creating app in run_mode: {run_mode}')

    # Load configuration based on the run mode
    app.config.from_object(config.get_named_config(run_mode))

    # Initialize Flask-SQLAlchemy with the app
    db.init_app(app)

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""
    def shell_context():
        """Shell context objects."""
        return {'app': app}

    app.shell_context_processor(shell_context)


def email_sender(target_system='SUBMIT'):
    """Send emails for submit or centre system."""
    if target_system == 'CENTRE':
        logger.info(f'Starting Centre Email Sending At {datetime.now()}')
        CentreMailer.send_mail()
    elif target_system == 'SUBMIT' or target_system is None or target_system == '':
        logger.info(f'Starting Submit Email Sending At {datetime.now()}')
        SubmitMailer.send_mail()
    else:
        logger.error(f'Invalid target_system "{target_system}". Must be SUBMIT or CENTRE.')
        raise ValueError(f'Invalid target_system: {target_system}')


def run(job_name, target_system=None, file_path=None):
    """Main function to run the job."""
    application = create_app()

    with application.app_context():
        if job_name == 'EXTRACT_PROJECT':
            # For SUBMIT, we must sync proponents first as they are dependencies
            if target_system == TargetSystem.SUBMIT:
                application.logger.info(f'Running Proponent Extractor for {target_system.value}...')
                ProponentExtractor.do_sync()
                application.logger.info(f'<<<< Completed Proponent Sync for {target_system.value} >>>')

            application.logger.info(f'Running Project Extractor for {target_system.value}...')
            ProjectExtractor.do_sync(target_system=target_system)
            application.logger.info(f'Completed Project Sync for {target_system.value}')

            # Update proponent eligibility status after project sync (SUBMIT only)
            if target_system == TargetSystem.SUBMIT:
                from epic_cron.models.db import init_submit_db
                application.logger.info('Running Proponent Status Updater...')
                ProponentStatusUpdater.update(init_submit_db(application))
                application.logger.info(f'<<<< Completed Proponent Status Update >>>>')

        elif job_name == 'SCAN_VIRUS':
            application.logger.info(f'Running Virus Scanner on: {file_path}')
            VirusScanner.scan_file_from_path(file_path)
            application.logger.info(f'Completed Virus Scan for {file_path}')

        elif job_name == 'EMAIL':
            application.logger.info(f'Starting Email Sending At {datetime.now()}')
            email_sender(target_system)
            application.logger.info(f'Completed Email Task')

        elif job_name == 'SYNC_CONDITION':
            application.logger.info(f'Starting Approved Condition Sync At {datetime.now()}')
            SyncApprovedCondition.sync_approved_condition()
            application.logger.info(f'Completed Sync Approved Condition')
        elif job_name == 'PENDING_ACCESS_REMINDER':
            from tasks.pending_access_reminder import PendingAccessReminder
            PendingAccessReminder.run()
            application.logger.info(f'<<<< Completed Pending Access Reminder >>>>')
        elif job_name == 'EXTRACT_WORK':
            application.logger.info(f'Running Project Extractor for SUBMIT before Work Extraction...')
            ProponentExtractor.do_sync()
            application.logger.info(f'<<<< Completed Proponent Sync for SUBMIT >>>>')
            ProjectExtractor.do_sync(target_system=TargetSystem.SUBMIT)
            application.logger.info(f'<<<< Completed Project Sync for SUBMIT >>>>')
            application.logger.info(f'Running Work Extractor at {datetime.now()}')
            WorkExtractor.do_sync()
            application.logger.info(f'<<<< Completed Work Extraction >>>>')
        elif job_name == 'EXTRACT_PHASE':
            application.logger.info(f'Running Phase Extractor at {datetime.now()}')
            PhaseExtractor.do_sync()
            application.logger.info(f'<<<< Completed Phase Extraction >>>>')

        else:
            application.logger.warning('No valid job_name passed. Exiting without running any tasks.')



if __name__ == "__main__":
    # No flags, just positional args
    args = sys.argv[1:]

    if not args:
        logger.error("You must provide a job type: SUBMIT/COMPLIANCE/EMAIL/SYNC_CONDITION/SCAN_VIRUS/EXTRACT_WORK/EXTRACT_PHASE")
        sys.exit(1)

    job_type = args[0]

    if job_type == "EMAIL":
        # EMAIL can have optional second arg for target system (CENTRE)
        target_system = args[1] if len(args) > 1 else None
        run("EMAIL", target_system=target_system)

    elif job_type == "SYNC_CONDITION":
        run("SYNC_CONDITION")

    elif job_type == "EXTRACT_WORK":
        run("EXTRACT_WORK")

    elif job_type == "EXTRACT_PHASE":
        run("EXTRACT_PHASE")

    elif job_type == "SCAN_VIRUS":
        if len(args) < 2:
            logger.error("You must provide a file path for SCAN_VIRUS.")
            sys.exit(1)
        file_path = args[1]
        run("SCAN_VIRUS", target_system=None, file_path=file_path)

    else:
        # Assume EXTRACT_PROJECT with target_system
        try:
            target_system = TargetSystem(job_type)
            run("EXTRACT_PROJECT", target_system)
        except ValueError:
            logger.error(f"Invalid job type '{job_type}'. Must be one of: SUBMIT, COMPLIANCE, EMAIL, SYNC_CONDITION, SCAN_VIRUS, EXTRACT_WORK, EXTRACT_PHASE")
            sys.exit(1)
