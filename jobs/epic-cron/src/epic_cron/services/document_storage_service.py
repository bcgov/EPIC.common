"""S3 operations used by background security scanning."""

import boto3
from flask import current_app


class DocumentStorageService:
    """Read and delete Submit documents directly from object storage."""

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

    def delete(self, object_key: str):
        """Remove an infected object from the bucket."""
        self.client.delete_object(Bucket=self.bucket, Key=object_key)
