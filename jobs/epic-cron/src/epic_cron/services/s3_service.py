"""Helpers for reading and managing files in S3-compatible storage."""

import boto3
from botocore.config import Config
from flask import current_app


class S3Service:
    """Thin wrapper around the boto3 S3 client."""

    def __init__(self):
        self.bucket_name = current_app.config["S3_BUCKET"]
        self.host = current_app.config.get("S3_HOST")
        self.client = boto3.client(
            "s3",
            aws_access_key_id=current_app.config["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["S3_SECRET_ACCESS_KEY"],
            region_name=current_app.config.get("S3_REGION") or None,
            endpoint_url=self._get_endpoint_url(),
            config=Config(
                connect_timeout=30,
                read_timeout=300,
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )

    def _get_endpoint_url(self):
        """Return a boto-compatible endpoint URL based on the shared S3 config."""
        if not self.host:
            return None
        if self.host.startswith("http://") or self.host.startswith("https://"):
            return self.host
        return f"https://{self.host}"

    def read_bytes(self, object_key: str) -> bytes:
        """Download an object and return its bytes."""
        response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
        return response["Body"].read()

    def copy_object(self, source_key: str, destination_key: str):
        """Copy an object within the configured bucket."""
        self.client.copy_object(
            Bucket=self.bucket_name,
            CopySource={"Bucket": self.bucket_name, "Key": source_key},
            Key=destination_key,
        )

    def delete_object(self, object_key: str):
        """Delete an object from the configured bucket."""
        self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
