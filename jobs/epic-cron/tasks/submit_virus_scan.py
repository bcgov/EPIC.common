"""Scheduled Submit document security scan."""

from epic_cron.services.submit_virus_scan_service import SubmitVirusScanService


class SubmitVirusScan:
    """Run the passive Submit upload scanner."""

    @staticmethod
    def run():
        SubmitVirusScanService.run()
