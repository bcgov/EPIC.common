import clamd
import io
from flask import current_app


class ClamAVService:
    """Service to scan files using ClamAV."""

    def __init__(self):
        """Initialize ClamAV connection from Flask config."""
        host = current_app.config.get("CLAMAV_HOST", "localhost")
        port = int(current_app.config.get("CLAMAV_PORT", 3310))
        self.cd = clamd.ClamdNetworkSocket(host=host, port=port)

    def scan_bytes(self, data: bytes):
        """Scan a byte stream and return result."""
        try:
            result = self.cd.instream(io.BytesIO(data))
            status, message = result.get("stream", ("ERROR", "Unknown"))
            if status == "FOUND":
                return True, message
            if status == "OK":
                return False, None
            return None, f"Unexpected response: {result}"
        except Exception as exc:
            return None, str(exc)
