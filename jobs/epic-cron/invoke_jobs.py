import os
import sys
import argparse
from datetime import datetime
from flask import Flask
from utils.logger import setup_logging
import config

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


def run(job_name, target_system=None, file_path=None, ssl_email_option=None):
    """Main function to run the job."""
    application = create_app()

    with application.app_context():
        if job_name == 'EXTRACT_PROJECT':
            from tasks.project_extractor import ProjectExtractor, TargetSystem
            from tasks.proponent_extractor import ProponentExtractor
            
            # For SUBMIT, we must sync proponents first as they are dependencies
            if target_system == TargetSystem.SUBMIT:
                print(f'Running Proponent Extractor for {target_system.value}...')
                ProponentExtractor.do_sync()
                application.logger.info(f'<<<< Completed Proponent Sync for {target_system.value} >>>')

            print(f'Running Project Extractor for {target_system.value}...')
            ProjectExtractor.do_sync(target_system=target_system)
            application.logger.info(f'<<<< Completed Project Sync for {target_system.value} >>>')

        elif job_name == 'SCAN_VIRUS':
            from tasks.virus_scanner import VirusScanner
            print(f'Running Virus Scanner on: {file_path}')
            VirusScanner.scan_file_from_path(file_path)
            application.logger.info(f'<<<< Completed Virus Scan for {file_path} >>>')

        elif job_name == 'EMAIL':
            if target_system == 'CENTRE':
                from tasks.centre_mail import CentreMailer

                application.logger.info(f'Starting Centre Email Sending At {datetime.now()}')
                CentreMailer.send_mail()
                application.logger.info('<<<< Completed Centre Email Task >>>>')
            else:
                from tasks.submit_mail import SubmitMailer

                application.logger.info(f'Starting Submit Email Sending At {datetime.now()}')
                SubmitMailer.send_mail()
                application.logger.info('<<<< Completed Submit Email Task >>>>')

        elif job_name == 'CHECK_SSL':
            from tasks.ssl_checker import SSLChecker
            print('Running weekly SSL workflow...')
            SSLChecker.run_weekly(force_email=ssl_email_option)
            application.logger.info('<<<< Completed Weekly SSL Workflow >>>')

        elif job_name == 'SSL_WEEKLY':
            from tasks.ssl_weekly_report import SSLWeeklyReport
            print('Generating Monthly SSL Digest...')
            SSLWeeklyReport.generate_report('monthly')
            application.logger.info('<<<< Completed Monthly SSL Digest >>>')

        elif job_name == 'SSL_FOLLOWUP':
            from tasks.ssl_weekly_report import SSLWeeklyReport
            print('Generating SSL Follow-up Digest...')
            SSLWeeklyReport.generate_report('followup')
            application.logger.info('<<<< Completed SSL Follow-up Digest >>>')

        else:
            application.logger.debug(f'No valid job_name passed: {job_name}. Exiting without running any tasks.')



if __name__ == "__main__":
    # No flags, just positional args
    args = sys.argv[1:]

    if not args:
        print(
            "ERROR: You must provide a target system, 'SCAN_VIRUS', 'EMAIL', "
            "'CHECK_SSL', 'SSL_WEEKLY', or 'SSL_FOLLOWUP'."
        )
        sys.exit(1)

    if args[0] == "SCAN_VIRUS":
        if len(args) < 2:
            print("ERROR: You must provide a file path for SCAN_VIRUS.")
            sys.exit(1)
        file_path = args[1]
        run("SCAN_VIRUS", target_system=None, file_path=file_path)

    elif args[0] == "EMAIL":
        target_system = args[1] if len(args) > 1 else None
        run("EMAIL", target_system=target_system)

    elif args[0] == "CHECK_SSL":
        ssl_email_option = args[1] if len(args) > 1 else None
        allowed_options = {"SEND_WEEKLY", "SEND_BIWEEKLY"}
        if ssl_email_option and ssl_email_option not in allowed_options:
            print("ERROR: CHECK_SSL optional flag must be SEND_WEEKLY or SEND_BIWEEKLY.")
            sys.exit(1)
        run("CHECK_SSL", ssl_email_option=ssl_email_option)

    elif args[0] == "SSL_WEEKLY":
        run("SSL_WEEKLY")

    elif args[0] == "SSL_FOLLOWUP":
        run("SSL_FOLLOWUP")

    else:
        # Assume EXTRACT_PROJECT with target_system
        from tasks.project_extractor import TargetSystem
        try:
            target_system = TargetSystem(args[0])
            run("EXTRACT_PROJECT", target_system)
        except ValueError:
            print(
                f"ERROR: Invalid target system '{args[0]}'. "
                f"Must be one of {[ts.value for ts in TargetSystem]} or "
                "EMAIL/CHECK_SSL/SSL_WEEKLY/SSL_FOLLOWUP"
            )
            sys.exit(1)
