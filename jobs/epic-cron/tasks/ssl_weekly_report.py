"""Queue friendly SSL digest emails for EPIC.centre staff."""
from datetime import datetime

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
        """Build actionable SSL items for the current month."""
        actionable = []
        for url in urls:
            if url.ssl_status == "Managed":
                continue

            item = None
            if url.ssl_status == "Error":
                item = SSLWeeklyReport._build_item(
                    url=url,
                    category="SSL Error",
                    expiry_date_label="Unknown",
                    days_remaining_label="Check now",
                )
            elif url.ssl_expiry:
                if url.ssl_expiry < now:
                    item = SSLWeeklyReport._build_item(
                        url=url,
                        category="Expired",
                        expiry_date_label=url.ssl_expiry.strftime("%Y-%m-%d"),
                        days_remaining_label="Expired",
                    )
                elif url.ssl_expiry < next_month_start:
                    days_left = max((url.ssl_expiry - now).days, 0)
                    item = SSLWeeklyReport._build_item(
                        url=url,
                        category="Due This Month",
                        expiry_date_label=url.ssl_expiry.strftime("%Y-%m-%d"),
                        days_remaining_label=f"{days_left} day(s) left",
                    )

            if item:
                actionable.append(item)

        actionable.sort(
            key=lambda item: (
                SSLWeeklyReport._category_order(item["category"]),
                item["app_name"],
                item["environment"],
            )
        )
        return actionable

    @staticmethod
    def _build_item(url, category, expiry_date_label, days_remaining_label):
        """Build a digest row for a single URL."""
        return {
            "app_name": url.app_name,
            "environment": url.environment or "Unknown",
            "url": url.url or "",
            "category": category,
            "ssl_status": url.ssl_status or "Unknown",
            "expiry_date": expiry_date_label,
            "days_remaining": days_remaining_label,
            "ticket_reference": url.ticket_reference or "",
            "renewal_status": (url.renewal_status or "NONE").replace("_", " ").title(),
            "renewal_comments": url.renewal_comments or "",
            "ssl_error_message": url.ssl_error_message or "",
        }

    @staticmethod
    def _build_summary(items):
        """Build digest counts for the email header."""
        expired_count = len([item for item in items if item["category"] == "Expired"])
        due_this_month_count = len(
            [item for item in items if item["category"] == "Due This Month"]
        )
        error_count = len([item for item in items if item["category"] == "SSL Error"])
        total_action_count = len(items)
        return {
            "expired_count": expired_count,
            "due_this_month_count": due_this_month_count,
            "error_count": error_count,
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
        """Sort expired first, then due this month, then SSL errors."""
        order = {
            "Expired": 0,
            "Due This Month": 1,
            "SSL Error": 2,
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
