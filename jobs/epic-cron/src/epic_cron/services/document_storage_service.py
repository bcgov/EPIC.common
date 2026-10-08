"""S3 operations used by background security scanning."""

import boto3
from botocore.exceptions import ClientError
from flask import current_app


class DocumentStorageService:
    """Read and quarantine Submit documents in object storage."""

    def __init__(self):
        config = current_app.config
        required_settings = ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_BUCKET")
        missing_settings = [name for name in required_settings if not config.get(name)]
        if missing_settings:
            raise ValueError(f"Missing S3 configuration: {', '.join(missing_settings)}")

        self.bucket = config["S3_BUCKET"]
        self.client = boto3.client(
            "s3",
            aws_access_key_id=config["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=config["S3_SECRET_ACCESS_KEY"],
            region_name=config.get("S3_REGION", "ca-central-1"),
            endpoint_url=self._endpoint_url(config.get("S3_HOST")),
        )

    @staticmethod
    def _endpoint_url(host: str | None) -> str | None:
        if not host or host.startswith(("http://", "https://")):
            return host
        return f"https://{host}"

    def read_bytes(self, object_key: str) -> bytes:
        """Read an object for scanning."""
        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        with response["Body"] as body:
            return body.read()

    def quarantine(self, object_key: str) -> str:
        """Rename an infected object in place and return its new key."""
        quarantined_key = self.quarantined_key(object_key)
        self.client.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": object_key},
            Key=quarantined_key,
        )
        self.client.delete_object(Bucket=self.bucket, Key=object_key)
        return quarantined_key

    def complete_started_quarantine(self, object_key: str) -> str | None:
        """Finish a quarantine whose S3 copy succeeded on an earlier run."""
        quarantined_key = self.quarantined_key(object_key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=quarantined_key)
        except ClientError as exc:
            if self.is_not_found(exc):
                return None
            raise

        self.client.delete_object(Bucket=self.bucket, Key=object_key)
        return quarantined_key

    @staticmethod
    def is_not_found(error: ClientError) -> bool:
        """Return whether S3 reports that an object key does not exist."""
        error_code = error.response.get("Error", {}).get("Code")
        return error_code in {"404", "NoSuchKey", "NotFound"}

    @staticmethod
    def quarantined_key(object_key: str) -> str:
        """Return the deterministic quarantine key in the original folder."""
        folder, separator, filename = object_key.rpartition("/")
        return f"{folder}{separator}virus_detected_{filename}"
