"""SSL Certificate Checker using secure cryptography library."""
import socket
import ssl
from datetime import datetime
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.orm import sessionmaker
from flask import current_app


class SSLChecker:
    """Check SSL certificates for URLs stored in the database."""

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
            # Query active URLs
            query = session.query(application_urls).filter(
                application_urls.c.is_active == True
            )
            urls = query.all()
            print(f"Found {len(urls)} URLs to check.")

            for app_url in urls:
                print(f"Checking {app_url.app_name} ({app_url.environment}): {app_url.url}")
                
                # Skip managed DevOps URLs
                if "devops.gov.bc.ca" in app_url.url:
                    print(f"Skipping SSL check for managed URL: {app_url.url}")
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status='Managed',
                        ssl_expiry=None,
                        ssl_error_message=None
                    )
                    continue

                # Check SSL certificate
                expiry_date, error_message = SSLChecker._get_ssl_expiry_date(app_url.url)
                
                if expiry_date:
                    ssl_status = SSLChecker._calculate_ssl_status(expiry_date)
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status=ssl_status,
                        ssl_expiry=expiry_date,
                        ssl_error_message=None
                    )
                else:
                    SSLChecker._update_url_status(
                        session, application_urls, app_url.id,
                        ssl_status='Error',
                        ssl_expiry=None,
                        ssl_error_message=error_message
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
        from datetime import timezone
        
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
    def _update_url_status(session, table, url_id, ssl_status, ssl_expiry, ssl_error_message):
        """Update SSL status for a URL."""
        update_stmt = table.update().where(
            table.c.id == url_id
        ).values(
            ssl_status=ssl_status,
            ssl_expiry=ssl_expiry,
            ssl_error_message=ssl_error_message,
            last_checked=datetime.utcnow()
        )
        session.execute(update_stmt)

    @staticmethod
    def _get_ssl_expiry_date(url):
        """
        Get SSL certificate expiry date using cryptography library.
        
        Returns:
            tuple: (expiry_date, error_message) where expiry_date is None if error occurred
        """
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or 443

        if not hostname:
            return None, "Invalid URL: no hostname"

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
                        return None, "No certificate returned"
                    
                    # Parse certificate and extract expiry date
                    cert = x509.load_der_x509_certificate(cert_bin, default_backend())
                    expiry_date = cert.not_valid_after_utc
                    
                    # Convert to datetime if needed (newer cryptography versions return datetime)
                    if not isinstance(expiry_date, datetime):
                        expiry_date = datetime.fromisoformat(str(expiry_date))
                    
                    return expiry_date, None

        except socket.gaierror:
            error_msg = f"DNS resolution failed for {hostname}"
            print(error_msg)
            return None, error_msg
        except socket.timeout:
            error_msg = f"Connection timeout to {hostname}"
            print(error_msg)
            return None, error_msg
        except ssl.SSLError as e:
            error_msg = f"SSL error for {hostname}: {str(e)}"
            print(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error fetching cert for {hostname}: {str(e)}"
            print(error_msg)
            return None, error_msg
