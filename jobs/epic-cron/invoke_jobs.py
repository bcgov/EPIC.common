import os
import sys
import argparse
from flask import Flask
from utils.logger import setup_logging
import config
from tasks.project_extractor import ProjectExtractor, TargetSystem  # Import the enum
from tasks.proponent_extractor import ProponentExtractor
from tasks.virus_scanner import VirusScanner

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    from epic_cron.models.db import init_db  # Import the correct methods

    app = Flask(__name__)
    print(f'>>>>> Creating app in run_mode: {run_mode}')

    # Load configuration based on the run mode
    app.config.from_object(config.CONFIGURATION.get(run_mode, 'production'))

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""
    def shell_context():
        """Shell context objects."""
        return {'app': app}

    app.shell_context_processor(shell_context)


def run(job_name, target_system=None, file_path=None):
    """Main function to run the job."""
    application = create_app()

    with application.app_context():
        if job_name == 'EXTRACT_PROJECT':
            # For SUBMIT, we must sync proponents first as they are dependencies
            if target_system == TargetSystem.SUBMIT:
                print(f'Running Proponent Extractor for {target_system.value}...')
                ProponentExtractor.do_sync()
                application.logger.info(f'<<<< Completed Proponent Sync for {target_system.value} >>>')

            print(f'Running Project Extractor for {target_system.value}...')
            ProjectExtractor.do_sync(target_system=target_system)
            application.logger.info(f'<<<< Completed Project Sync for {target_system.value} >>>')

        elif job_name == 'SCAN_VIRUS':
            print(f'Running Virus Scanner on: {file_path}')
            VirusScanner.scan_file_from_path(file_path)
            application.logger.info(f'<<<< Completed Virus Scan for {file_path} >>>')

        else:
            application.logger.debug('No valid job_name passed. Exiting without running any tasks.')



if __name__ == "__main__":
    # No flags, just positional args
    args = sys.argv[1:]

    if not args:
        print("ERROR: You must provide either a target system (SUBMIT/COMPLIANCE) or 'SCAN_VIRUS' + file path.")
        sys.exit(1)

    if args[0] == "SCAN_VIRUS":
        if len(args) < 2:
            print("ERROR: You must provide a file path for SCAN_VIRUS.")
            sys.exit(1)
        file_path = args[1]
        run("SCAN_VIRUS", target_system=None, file_path=file_path)

    else:
        # Assume EXTRACT_PROJECT with target_system
        try:
            target_system = TargetSystem(args[0])
            run("EXTRACT_PROJECT", target_system)
        except ValueError:
            print(f"ERROR: Invalid target system '{args[0]}'. Must be one of {[ts.value for ts in TargetSystem]}")
            sys.exit(1)

