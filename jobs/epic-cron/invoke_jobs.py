import os
import sys
import argparse
from flask import Flask
from utils.logger import setup_logging
import config
from tasks.project_extractor import ProjectExtractor, TargetSystem  # Import the enum

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


def run(job_name, target_system):
    """Main function to run the job."""
    # Create the Flask app
    application = create_app()

    # Push the app context to ensure the Flask app is available during task execution
    with application.app_context():
        if job_name == 'EXTRACT_PROJECT':
            print(f'Running Project Extractor for {target_system.value}...')
            ProjectExtractor.do_sync(target_system=target_system)
            application.logger.info(f'<<<< Completed Project Sync for {target_system.value} >>>')
        else:
            application.logger.debug('No valid job_name passed. Exiting without running any tasks.')


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run Project Extractor jobs.")
    parser.add_argument(
        'target_system',
        type=str,
        choices=[system.value for system in TargetSystem],
        help="Target system for the job (e.g., SUBMIT or COMPLIANCE)"
    )
    args = parser.parse_args()

    # Map the string argument to the TargetSystem enum
    target_system = TargetSystem(args.target_system)

    # Run the job
    run('EXTRACT_PROJECT', target_system)
