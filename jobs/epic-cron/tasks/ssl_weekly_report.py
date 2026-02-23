from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.orm import sessionmaker, declarative_base
from flask import current_app
import json

# Define minimal ApplicationUrl model for reading
Base = declarative_base()

class ApplicationUrl(Base):
    __tablename__ = 'application_urls'
    id = Column(Integer, primary_key=True)
    app_name = Column(String(100))
    environment = Column(String(50))
    url = Column(String(500))
    ssl_expiry = Column(DateTime)
    ssl_status = Column(String(50))
    is_active = Column(Boolean)

class SSLWeeklyReport:
    @staticmethod
    def generate_report():
        db_uri = current_app.config.get('CENTRE_DATABASE_URI')
        if not db_uri:
            print("CENTRE_DATABASE_URI not found in config")
            return

        engine = create_engine(db_uri)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # 1. Fetch all active URLs
            urls = session.query(ApplicationUrl).filter_by(is_active=True).all()
            print(f"Found {len(urls)} active URLs.")

            expiring_urls = []
            now = datetime.utcnow()
            warning_threshold = now + timedelta(days=30)

            # 2. Identify expiring/expired
            for url in urls:
                if not url.ssl_expiry:
                    # Treat unknown/missing expiry as "Error" or just skip? 
                    # Let's verify status.
                    if url.ssl_status == 'Error':
                         expiring_urls.append({
                            "app_name": url.app_name,
                            "environment": url.environment,
                            "url": url.url,
                            "expiry_date": "Unknown (Error)",
                            "status": "Error"
                        })
                    continue

                if url.ssl_expiry < warning_threshold:
                    status = "Expired" if url.ssl_expiry < now else "Expiring Soon"
                    expiring_urls.append({
                        "app_name": url.app_name,
                        "environment": url.environment,
                        "url": url.url,
                        "expiry_date": url.ssl_expiry.strftime('%Y-%m-%d'),
                        "status": status
                    })

            # 3. Construct Payload
            # Who receives this? For now, let's use a config email or a hardcoded default, 
            # ideally fetched from a "System Settings" or ENV.
            # Using a placeholder 'EPIC_ADMIN_EMAIL' from config, defaulting to devops.
            admin_email = current_app.config.get('EPIC_ADMIN_EMAIL', 'EPIC.Devops@gov.bc.ca')
            
            payload = {
                "recipients": [admin_email],
                "report_date": now.strftime('%b %d, %Y'),
                "expiring_urls": expiring_urls,
                "centre_url": current_app.config.get('WEB_URL', 'https://epic-centre.gov.bc.ca'),
                "sender": "EPIC.centre@gov.bc.ca"
            }

            # 4. Insert into Email Queue
            # We need to insert into the 'email_queue' table. This table might be in the SAME database as centre-api.
            # Let's insert raw SQL to avoid model dependency issues if models vary.
            
            insert_stmt = text("""
                INSERT INTO email_queue (template_name, status, payload, created_at, updated_at)
                VALUES (:template, 'PENDING', :payload, :now, :now)
            """)
            
            session.execute(insert_stmt, {
                "template": "ssl_expiry_report.html",
                "payload": json.dumps(payload),
                "now": now
            })
            
            session.commit()
            print(f"Weekly report generated. Found {len(expiring_urls)} issues. Email queued for {admin_email}.")

        except Exception as e:
            print(f"Error generating weekly report: {e}")
            session.rollback()
        finally:
            session.close()
