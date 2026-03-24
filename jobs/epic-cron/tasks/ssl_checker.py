"""SSL Certificate Checker using secure cryptography library."""
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import create_engine, Table, MetaData, and_, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from flask import current_app


class SSLChecker:
    """Check SSL certificates for URLs stored in the database."""

    @staticmethod
    def run(force_email=None):
        """Run the SSL workflow: update data, then queue a scheduled digest if needed."""
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
            # Restrict protocol versions to TLS 1.2 or higher
            if hasattr(ssl, "TLSVersion"):
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                if hasattr(ssl.TLSVersion, "MAXIMUM_SUPPORTED"):
                    context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
            else:
                if hasattr(ssl, "OP_NO_TLSv1"):
                    context.options |= ssl.OP_NO_TLSv1
                if hasattr(ssl, "OP_NO_TLSv1_1"):
                    context.options |= ssl.OP_NO_TLSv1_1
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
        """Queue the monthly or follow-up digest based on the current day of month."""
        now = now or datetime.utcnow()

        if force_email == "SEND_WEEKLY":
            print("Forced monthly SSL digest requested.")
            SSLChecker._queue_digest(report_type="monthly", now=now)
            return

        if force_email == "SEND_BIWEEKLY":
            print("Forced SSL follow-up digest requested.")
            SSLChecker._queue_digest(report_type="followup", now=now)
            return

        day_of_month = now.day

        if day_of_month <= 7:
            print("Start-of-month run detected. Queueing monthly SSL digest.")
            SSLChecker._queue_digest(report_type="monthly", now=now)
            return

        if day_of_month <= 14:
            print("Mid-month run detected. Queueing SSL follow-up digest if needed.")
            SSLChecker._queue_digest(report_type="followup", now=now)
            return

        print("No SSL digest scheduled for this run.")

    @staticmethod
    def _queue_digest(report_type, now=None):
        """Queue a concise monthly SSL digest email."""
        db_uri = current_app.config.get("CENTRE_DATABASE_URI")
        if not db_uri:
            print("CENTRE_DATABASE_URI not found in config")
            return

        now = now or datetime.utcnow()
        month_start = SSLChecker._month_start(now)
        next_month_start = SSLChecker._next_month_start(month_start)
        month_label = month_start.strftime("%B %Y")
        month_key = month_start.strftime("%Y-%m")
        environment_label = (current_app.config.get("ENVIRONMENT", "") or "").strip()

        engine = create_engine(db_uri)
        metadata = MetaData()
        application_urls = Table("application_urls", metadata, autoload_with=engine)
        email_queue = Table("email_queue", metadata, autoload_with=engine)
        session = sessionmaker(bind=engine)()

        try:
            if SSLChecker._digest_already_queued(
                session=session,
                email_queue=email_queue,
                report_type=report_type,
                month_key=month_key,
            ):
                print(f"SSL {report_type} digest already queued for {month_key}. Skipping.")
                return

            urls = session.query(application_urls).filter(
                application_urls.c.is_active == True
            ).all()
            items = SSLChecker._build_digest_items(urls=urls, now=now, next_month_start=next_month_start)
            summary = SSLChecker._build_summary(items)
            all_clear = summary["total_action_count"] == 0

            if report_type == "followup" and all_clear:
                print(f"No outstanding SSL items for follow-up in {month_key}. Skipping.")
                return

            recipients = SSLChecker._get_recipients()
            if not recipients:
                print("SSL_NOTIFICATION_RECIPIENTS is not configured. Skipping SSL digest queue.")
                return

            payload = {
                "recipients": recipients,
                "sender": current_app.config.get("SSL_NOTIFICATION_SENDER", "EPIC.centre@gov.bc.ca"),
                "centre_url": current_app.config.get("EPIC_CENTRE_WEB_URL", "https://centre.eao.gov.bc.ca/application-urls"),
                "generated_at": now.strftime("%b %d, %Y"),
                "report_type": report_type,
                "report_month_label": month_label,
                "report_month_key": month_key,
                "environment_label": environment_label,
                "all_clear": all_clear,
                "summary": summary,
                "items": items,
            }

            session.execute(
                email_queue.insert().values(
                    template_name="ssl_digest_notification.html",
                    status="PENDING",
                    payload=payload,
                    created_at=now,
                )
            )
            session.commit()
            print(
                f"Queued SSL {report_type} digest for {month_label} "
                f"with {summary['total_action_count']} actionable item(s)."
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error generating SSL digest: {exc}")
            session.rollback()
        finally:
            session.close()

    @staticmethod
    def _build_digest_items(urls, now, next_month_start):
        """Build concise SSL items expiring this month, grouped by certificate host."""
        items = []
        for group in SSLChecker._group_urls_by_certificate(urls):
            representative = SSLChecker._select_representative_url(group["urls"])
            if representative.ssl_status == "Managed" or not representative.ssl_expiry:
                continue

            if representative.ssl_expiry < now:
                category = "Expired"
                days_label = "Expired"
            elif representative.ssl_expiry < next_month_start:
                category = "Expiring This Month"
                days_left = max((representative.ssl_expiry - now).days, 0)
                days_label = f"{days_left} day(s) left"
            else:
                continue

            items.append(
                {
                    "certificate_host": group["host"],
                    "category": category,
                    "expiry_date": representative.ssl_expiry.strftime("%Y-%m-%d"),
                    "days_remaining": days_label,
                    "linked_routes": [
                        {
                            "app_name": url.app_name,
                            "environment": url.environment or "Unknown",
                            "url": url.url or "",
                        }
                        for url in group["urls"]
                    ],
                }
            )

        items.sort(key=lambda item: (SSLChecker._category_order(item["category"]), item["certificate_host"]))
        return items

    @staticmethod
    def _build_summary(items):
        """Build email summary counts."""
        return {
            "expired_count": len([item for item in items if item["category"] == "Expired"]),
            "due_this_month_count": len([item for item in items if item["category"] == "Expiring This Month"]),
            "total_action_count": len(items),
        }

    @staticmethod
    def _digest_already_queued(session, email_queue, report_type, month_key):
        """Avoid duplicate monthly/follow-up emails for the same month."""
        return (
            session.query(email_queue.c.id)
            .filter(
                email_queue.c.template_name == "ssl_digest_notification.html",
                email_queue.c.status.in_(("PENDING", "SENT")),
                and_(
                    func.coalesce(email_queue.c.payload["report_type"].astext, "") == report_type,
                    func.coalesce(email_queue.c.payload["report_month_key"].astext, "") == month_key,
                ),
            )
            .first()
            is not None
        )

    @staticmethod
    def _get_recipients():
        """Return configured SSL digest recipients."""
        configured = current_app.config.get("SSL_NOTIFICATION_RECIPIENTS", "")
        return configured if isinstance(configured, list) else [
            email.strip() for email in configured.split(",") if email.strip()
        ]

    @staticmethod
    def _group_urls_by_certificate(urls):
        """Group rows by certificate origin so shared host certs are handled once."""
        groups = {}
        for url in urls:
            origin, host = SSLChecker._get_certificate_origin(url.url)
            key = origin.lower()
            if key not in groups:
                groups[key] = {"origin": origin, "host": host, "urls": []}
            groups[key]["urls"].append(url)
        return list(groups.values())

    @staticmethod
    def _get_certificate_origin(url):
        """Return the origin used to identify a shared certificate."""
        parsed = urlparse(url or "")
        if not parsed.scheme or not parsed.hostname:
            return (url or "Unknown URL"), (url or "Unknown URL")
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme.lower()}://{parsed.hostname}{port}", f"{parsed.hostname}{port}"

    @staticmethod
    def _inherits_ssl_from_host(url):
        """Return True when the route inherits SSL from a host-level certificate."""
        parsed = urlparse(url or "")
        return bool(parsed.hostname and parsed.path and parsed.path not in ("", "/"))

    @staticmethod
    def _select_representative_url(urls):
        """Pick the row that best represents the certificate group."""
        return sorted(
            urls,
            key=lambda url: (
                SSLChecker._status_priority(url.ssl_status),
                0 if SSLChecker._has_tracking_data(url) else 1,
                0 if not SSLChecker._inherits_ssl_from_host(url.url) else 1,
                url.app_name or "",
                url.environment or "",
            ),
        )[0]

    @staticmethod
    def _has_tracking_data(url):
        """Return True when the row has staff-entered renewal metadata."""
        return bool(
            (getattr(url, "ticket_reference", None) and url.ticket_reference.strip())
            or (getattr(url, "renewal_comments", None) and url.renewal_comments.strip())
            or ((getattr(url, "renewal_status", "NONE") or "NONE") != "NONE")
        )

    @staticmethod
    def _status_priority(status):
        """Rank urgent SSL states first."""
        order = {
            "Expired": 0,
            "Error": 1,
            "Expiring Soon": 2,
            "Valid": 3,
            "Managed": 4,
        }
        return order.get(status or "Unknown", 99)

    @staticmethod
    def _month_start(now):
        """Start of the current UTC month."""
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _next_month_start(month_start):
        """Start of the next UTC month."""
        if month_start.month == 12:
            return month_start.replace(year=month_start.year + 1, month=1)
        return month_start.replace(month=month_start.month + 1)

    @staticmethod
    def _category_order(category):
        """Sort expired first, then expiring this month."""
        order = {"Expired": 0, "Expiring This Month": 1}
        return order.get(category, 99)
