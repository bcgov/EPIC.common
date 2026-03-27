from flask import current_app

from epic_cron.services.clamav_service import ClamAVService
from epic_cron.services.submit_virus_scan_service import SubmitVirusScanService


class VirusScanner:
    """Virus scanning task helpers."""

    @staticmethod
    def scan_file_from_path(file_path: str):
        """Scan a local file path."""
        print(f"Scanning file: {file_path}")
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            clam = ClamAVService()
            infected, info = clam.scan_bytes(data)

            if infected is True:
                current_app.logger.warning(f"Virus detected: {info}")
            elif infected is False:
                current_app.logger.info("File is clean.")
            else:
                current_app.logger.warning(f"Scan failed or unknown result: {info}")
        except Exception as e:
            current_app.logger.error(f"Error scanning file: {e}")

    @staticmethod
    def scan_submit_uploads():
        """Scan recent EPIC.submit uploads."""
        return SubmitVirusScanService.scan_recent_uploads()
