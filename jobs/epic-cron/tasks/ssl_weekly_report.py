"""Queue friendly SSL digest emails for EPIC.centre staff."""
from datetime import datetime
from urllib.parse import urlparse

from flask import current_app
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, and_, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()

SSL_DIGEST_TEMPLATE = "ssl_digest_notification.html"
REPORT_TYPE_MONTHLY = "monthly"
REPORT_TYPE_FOLLOWUP = "followup"


class ApplicationUrl(Base):
    """Minimal application_urls model for digest generation."""

    __tablename__ = "application_urls"

    id = Column(Integer, primary_key=True)
    app_name = Column(String(100))
    environment = Column(String(50))
    url = Column(String(500))
    ssl_expiry = Column(DateTime)
    ssl_status = Column(String(50))
    ssl_error_message = Column(String(500))
    ticket_reference = Column(String(50))
    renewal_status = Column(String(50))
    renewal_comments = Column(Text)
    is_active = Column(Boolean)


class EmailQueue(Base):
    """Minimal email_queue model for duplicate checks and queueing."""

    __tablename__ = "email_queue"

    id = Column(Integer, primary_key=True)
    template_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False)


class SSLWeeklyReport:
    """Backwards-compatible entry point for SSL digest jobs."""

    @staticmethod
    def generate_report(report_type=REPORT_TYPE_MONTHLY):
        """Queue a monthly or follow-up SSL digest email."""
        db_uri = current_app.config.get("CENTRE_DATABASE_URI")
        if not db_uri:
            print("CENTRE_DATABASE_URI not found in config")
            return

        engine = create_engine(db_uri)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            now = datetime.utcnow()
            month_start = SSLWeeklyReport._month_start(now)
            next_month_start = SSLWeeklyReport._next_month_start(month_start)
            month_label = month_start.strftime("%B %Y")
            month_key = month_start.strftime("%Y-%m")
            environment_label = (current_app.config.get("ENVIRONMENT", "") or "").strip()

            if SSLWeeklyReport._digest_already_queued(
                session,
                report_type=report_type,
                month_key=month_key,
            ):
                print(f"SSL {report_type} digest already queued for {month_key}. Skipping.")
                return

            urls = session.query(ApplicationUrl).filter_by(is_active=True).all()
            print(f"Found {len(urls)} active URLs.")

            digest_items = SSLWeeklyReport._build_digest_items(
                urls=urls,
                now=now,
                next_month_start=next_month_start,
            )
            summary = SSLWeeklyReport._build_summary(digest_items)
            all_clear = summary["total_action_count"] == 0

            if report_type == REPORT_TYPE_FOLLOWUP and all_clear:
                print(f"No outstanding SSL items for follow-up in {month_key}. Skipping.")
                return

            payload = {
                "recipients": SSLWeeklyReport._get_recipients(),
                "sender": current_app.config.get(
                    "SSL_NOTIFICATION_SENDER",
                    "EPIC.centre@gov.bc.ca",
                ),
                "centre_url": current_app.config.get(
                    "EPIC_CENTRE_WEB_URL",
                    "https://centre.eao.gov.bc.ca/application-urls",
                ),
                "generated_at": now.strftime("%b %d, %Y"),
                "report_type": report_type,
                "report_month_label": month_label,
                "report_month_key": month_key,
                "environment_label": environment_label,
                "all_clear": all_clear,
                "summary": summary,
                "items": digest_items,
            }

            email_queue = EmailQueue(
                template_name=SSL_DIGEST_TEMPLATE,
                status="PENDING",
                payload=payload,
                created_at=now,
            )
            session.add(email_queue)
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
        """Build SSL items expiring this month, grouped by certificate host."""
        actionable = []
        grouped_urls = SSLWeeklyReport._group_urls_by_certificate(urls)

        for certificate_group in grouped_urls:
            representative = SSLWeeklyReport._select_representative_url(certificate_group["urls"])
            if representative.ssl_status == "Managed":
                continue

            item = None
            if representative.ssl_expiry:
                if representative.ssl_expiry < now:
                    item = SSLWeeklyReport._build_item(
                        certificate_group=certificate_group,
                        category="Expired",
                        expiry_date_label=representative.ssl_expiry.strftime("%Y-%m-%d"),
                        days_remaining_label="Expired",
                    )
                elif representative.ssl_expiry < next_month_start:
                    days_left = max((representative.ssl_expiry - now).days, 0)
                    item = SSLWeeklyReport._build_item(
                        certificate_group=certificate_group,
                        category="Expiring This Month",
                        expiry_date_label=representative.ssl_expiry.strftime("%Y-%m-%d"),
                        days_remaining_label=f"{days_left} day(s) left",
                    )

            if item:
                actionable.append(item)

        actionable.sort(
            key=lambda item: (
                SSLWeeklyReport._category_order(item["category"]),
                item["certificate_host"],
            )
        )
        return actionable

    @staticmethod
    def _build_item(certificate_group, category, expiry_date_label, days_remaining_label):
        """Build a digest row for a certificate group."""
        representative = SSLWeeklyReport._select_representative_url(certificate_group["urls"])
        linked_routes = []
        for url in certificate_group["urls"]:
            linked_routes.append(
                {
                    "app_name": url.app_name,
                    "environment": url.environment or "Unknown",
                    "url": url.url or "",
                    "inherits_ssl": SSLWeeklyReport._inherits_ssl_from_host(url.url),
                }
            )

        return {
            "certificate_host": certificate_group["host"],
            "certificate_url": certificate_group["origin"],
            "category": category,
            "expiry_date": expiry_date_label,
            "days_remaining": days_remaining_label,
            "linked_routes": linked_routes,
            "linked_route_count": len(linked_routes),
            "linked_app_count": len({url.app_name for url in certificate_group["urls"]}),
            "representative_url": representative.url or "",
        }

    @staticmethod
    def _build_summary(items):
        """Build digest counts for the email header."""
        expired_count = len([item for item in items if item["category"] == "Expired"])
        due_this_month_count = len(
            [item for item in items if item["category"] == "Expiring This Month"]
        )
        total_action_count = len(items)
        return {
            "expired_count": expired_count,
            "due_this_month_count": due_this_month_count,
            "total_action_count": total_action_count,
        }

    @staticmethod
    def _digest_already_queued(session, report_type, month_key):
        """Avoid duplicate monthly/follow-up queue rows for the same month."""
        existing = (
            session.query(EmailQueue.id)
            .filter(
                EmailQueue.template_name == SSL_DIGEST_TEMPLATE,
                EmailQueue.status.in_(("PENDING", "SENT")),
                and_(
                    func.coalesce(
                        EmailQueue.payload["report_type"].astext, ""
                    )
                    == report_type,
                    func.coalesce(
                        EmailQueue.payload["report_month_key"].astext, ""
                    )
                    == month_key,
                ),
            )
            .first()
        )
        return existing is not None

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
        order = {
            "Expired": 0,
            "Expiring This Month": 1,
        }
        return order.get(category, 99)

    @staticmethod
    def _get_recipients():
        """Return configured SSL digest recipients."""
        configured = current_app.config.get(
            "SSL_NOTIFICATION_RECIPIENTS",
            "",
        )
        recipients = configured if isinstance(configured, list) else [
            email.strip() for email in configured.split(",") if email.strip()
        ]

        if recipients:
            return recipients

        fallback = current_app.config.get("DST_EMAIL", "EPIC.Devops@gov.bc.ca")
        return [fallback] if fallback else ["EPIC.Devops@gov.bc.ca"]

    @staticmethod
    def _group_urls_by_certificate(urls):
        """Group URLs by certificate origin so shared host certs are reported once."""
        grouped = {}
        for url in urls:
            origin, host = SSLWeeklyReport._get_certificate_origin(url.url)
            key = origin.lower()
            if key not in grouped:
                grouped[key] = {
                    "origin": origin,
                    "host": host,
                    "urls": [],
                }
            grouped[key]["urls"].append(url)

        return list(grouped.values())

    @staticmethod
    def _get_certificate_origin(url):
        """Return the URL origin used to determine shared host certificates."""
        parsed = urlparse(url or "")
        if not parsed.scheme or not parsed.hostname:
            return (url or "Unknown URL"), (url or "Unknown URL")

        port = f":{parsed.port}" if parsed.port else ""
        origin = f"{parsed.scheme.lower()}://{parsed.hostname}{port}"
        host = f"{parsed.hostname}{port}"
        return origin, host

    @staticmethod
    def _inherits_ssl_from_host(url):
        """Return True when the route inherits SSL from a host-level certificate."""
        parsed = urlparse(url or "")
        return bool(parsed.hostname and parsed.path and parsed.path not in ("", "/"))

    @staticmethod
    def _select_representative_url(urls):
        """Pick the row that best represents the certificate group for renewal tracking."""
        return sorted(
            urls,
            key=lambda url: (
                SSLWeeklyReport._status_priority(url.ssl_status),
                0 if SSLWeeklyReport._has_tracking_data(url) else 1,
                0 if not SSLWeeklyReport._inherits_ssl_from_host(url.url) else 1,
                url.app_name or "",
                url.environment or "",
            ),
        )[0]

    @staticmethod
    def _has_tracking_data(url):
        """Return True when the row has renewal metadata entered by staff."""
        return bool(
            (url.ticket_reference and url.ticket_reference.strip())
            or (url.renewal_comments and url.renewal_comments.strip())
            or ((url.renewal_status or "NONE") != "NONE")
        )

    @staticmethod
    def _status_priority(status):
        """Rank the most urgent SSL status first."""
        order = {
            "Expired": 0,
            "Error": 1,
            "Expiring Soon": 2,
            "Valid": 3,
            "Managed": 4,
        }
        return order.get(status or "Unknown", 99)
