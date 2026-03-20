"""SSL Certificate Checker using secure cryptography library."""
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.orm import sessionmaker
from flask import current_app


class SSLChecker:
    """Check SSL certificates for URLs stored in the database."""

    @staticmethod
    def run_weekly(force_email=None):
        """Run the weekly SSL workflow: update data, then queue a scheduled digest if needed."""
        SSLChecker.check_ssl()
        SSLChecker._queue_scheduled_digest(force_email=force_email)

    @staticmethod
    def check_ssl():
        """Check SSL certificates for all active application URLs."""
        db_uri = current_app.config.get('CENTRE_DATABASE_URI')
        if not db_uri:
            print("CENTRE_DATABASE_URI not found in config")
            return

        engine = create_engine(db_uri)
        metadata = MetaData()
        
        # Use reflection instead of duplicate model definition
        application_urls = Table('application_urls', metadata, autoload_with=engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            cert_cache = {}

            # Query active URLs
            query = session.query(application_urls).filter(
                application_urls.c.is_active == True
            )
            urls = query.all()
            print(f"Found {len(urls)} URLs to check.")

            for app_url in urls:
                print(f"Checking {app_url.app_name} ({app_url.environment}): {app_url.url}")

                certificate_target = SSLChecker._get_certificate_target(app_url.url)

                # Skip managed DevOps URLs
                if "devops.gov.bc.ca" in certificate_target:
                    print(f"Skipping SSL check for managed URL: {app_url.url}")
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status='Managed',
                        ssl_expiry=None,
                        ssl_error_message=None
                    )
                    continue

                # Reuse the same certificate lookup for routes on the same host.
                if certificate_target not in cert_cache:
                    cert_cache[certificate_target] = SSLChecker._get_ssl_details(certificate_target)
                cert_details = cert_cache[certificate_target]
                
                if cert_details['ssl_expiry']:
                    ssl_status = SSLChecker._calculate_ssl_status(cert_details['ssl_expiry'])
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status=ssl_status,
                        ssl_expiry=cert_details['ssl_expiry'],
                        ssl_error_message=None
                    )
                else:
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status='Error',
                        ssl_expiry=None,
                        ssl_error_message=cert_details['ssl_error_message']
                    )
            
            session.commit()
            print("SSL Check completed.")

        except Exception as e:
            print(f"Database error: {e}")
            session.rollback()
        finally:
            session.close()

    @staticmethod
    def _calculate_ssl_status(expiry_date):
        """Calculate SSL status based on expiry date."""
        # Use timezone-aware datetime for comparison
        now = datetime.now(timezone.utc)
        
        # Make sure expiry_date is timezone-aware (should be from cryptography)
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        
        days_left = (expiry_date - now).days
        
        if days_left < 0:
            return 'Expired'
        elif days_left < 30:
            return 'Expiring Soon'
        else:
            return 'Valid'

    @staticmethod
    def _update_url_status(session, table, url_id, **values):
        """Update SSL status for a URL."""
        update_stmt = table.update().where(
            table.c.id == url_id
        ).values(
            **values,
            last_checked=datetime.utcnow()
        )
        session.execute(update_stmt)

    @staticmethod
    def _get_ssl_details(url):
        """Return normalized SSL certificate details for a URL."""
        result = {
            'ssl_expiry': None,
            'ssl_error_message': None,
        }
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or 443
        scheme = parsed_url.scheme.lower() if parsed_url.scheme else 'https'

        if not hostname:
            result['ssl_error_message'] = "Invalid URL: no hostname"
            return result
        if scheme != 'https':
            result['ssl_error_message'] = f"Unsupported scheme for SSL check: {scheme}"
            return result

        try:
            # Create SSL context that doesn't verify certificates
            # We only want to read the expiry date, not validate the cert
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert_bin = ssock.getpeercert(binary_form=True)
                    if not cert_bin:
                        result['ssl_error_message'] = "No certificate returned"
                        return result
                    
                    # Parse certificate and extract expiry date
                    cert = x509.load_der_x509_certificate(cert_bin, default_backend())
                    result['ssl_expiry'] = SSLChecker._normalize_datetime(cert.not_valid_after_utc)
                    return result

        except socket.gaierror:
            result['ssl_error_message'] = f"DNS resolution failed for {hostname}"
        except socket.timeout:
            result['ssl_error_message'] = f"Connection timeout to {hostname}"
        except ssl.SSLError as e:
            result['ssl_error_message'] = f"SSL error for {hostname}: {str(e)}"
        except Exception as e:
            result['ssl_error_message'] = f"Error fetching cert for {hostname}: {str(e)}"

        print(result['ssl_error_message'])
        return result

    @staticmethod
    def _normalize_datetime(value):
        """Normalize aware datetimes to naive UTC for storage in centre DB."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _get_certificate_target(url):
        """Return the origin used for certificate checks so path-based routes share one lookup."""
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.hostname:
            return url

        port = f":{parsed_url.port}" if parsed_url.port else ""
        return f"{parsed_url.scheme.lower()}://{parsed_url.hostname}{port}"

    @staticmethod
    def _queue_scheduled_digest(now=None, force_email=None):
        """Queue the monthly or follow-up digest based on the current week of month."""
        from tasks.ssl_weekly_report import REPORT_TYPE_FOLLOWUP, REPORT_TYPE_MONTHLY, SSLWeeklyReport

        now = now or datetime.utcnow()

        print('--force_emailforce_emailforce_email-------',force_email)
        if force_email == "SEND_WEEKLY":
            print("Forced monthly SSL digest requested.")
            SSLWeeklyReport.generate_report(REPORT_TYPE_MONTHLY)
            return

        if force_email == "SEND_BIWEEKLY":
            print("Forced SSL follow-up digest requested.")
            SSLWeeklyReport.generate_report(REPORT_TYPE_FOLLOWUP)
            return

        day_of_month = now.day

        if day_of_month <= 7:
            print("Start-of-month weekly run detected. Queueing monthly SSL digest.")
            SSLWeeklyReport.generate_report(REPORT_TYPE_MONTHLY)
            return

        if day_of_month <= 14:
            print("Second weekly run of the month detected. Queueing SSL follow-up digest if needed.")
            SSLWeeklyReport.generate_report(REPORT_TYPE_FOLLOWUP)
            return

        print("No SSL digest scheduled for this weekly run.")
