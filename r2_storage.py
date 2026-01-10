"""
Cloudflare R2 Storage Service

Provides time-limited shared content via presigned URLs.
Uses S3-compatible API for Cloudflare R2.
"""

import os
import uuid
import logging
from typing import Optional, Tuple
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars

logger = logging.getLogger(__name__)


class R2StorageService:
    """Service for uploading content to Cloudflare R2 and generating presigned URLs."""

    def __init__(self):
        """Initialize R2 storage service with credentials from environment."""
        self.account_id = os.getenv('R2_ACCOUNT_ID')
        self.access_key = os.getenv('R2_ACCESS_KEY_ID')
        self.secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket = os.getenv('R2_BUCKET', 'ichra-shared')
        # R2 presigned URLs max out at 7 days (604800 seconds)
        self.default_expiry_days = min(int(os.getenv('QR_LINK_EXPIRY_DAYS', '7')), 7)

        if self.account_id:
            self.endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
        else:
            self.endpoint = None

    def is_configured(self) -> Tuple[bool, Optional[str]]:
        """Check if R2 is properly configured.

        Returns:
            Tuple of (is_configured, error_message)
        """
        if not self.account_id:
            return False, "R2_ACCOUNT_ID not set"
        if not self.access_key:
            return False, "R2_ACCESS_KEY_ID not set"
        if not self.secret_key:
            return False, "R2_SECRET_ACCESS_KEY not set"
        return True, None

    def _get_client(self):
        """Get boto3 S3 client configured for R2."""
        import boto3
        from botocore.config import Config

        return boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'  # R2 uses 'auto' region
        )

    def upload_html(
        self,
        html_content: str,
        expiry_days: Optional[int] = None,
        prefix: str = "breakdowns"
    ) -> Optional[str]:
        """Upload HTML content to R2 and return presigned URL.

        Args:
            html_content: HTML string to upload
            expiry_days: Days until URL expires (default from env or 14)
            prefix: Key prefix/folder in bucket

        Returns:
            Presigned URL string, or None if upload fails
        """
        is_configured, error = self.is_configured()
        if not is_configured:
            logger.warning(f"R2 not configured: {error}")
            return None

        if expiry_days is None:
            expiry_days = self.default_expiry_days
        # R2 presigned URLs max out at 7 days
        expiry_days = min(expiry_days, 7)

        try:
            client = self._get_client()

            # Generate unique key with timestamp for debugging
            timestamp = datetime.now().strftime("%Y%m%d")
            unique_id = uuid.uuid4()
            key = f"{prefix}/{timestamp}/{unique_id}.html"

            # Upload HTML content
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=html_content.encode('utf-8'),
                ContentType='text/html; charset=utf-8',
                CacheControl='no-cache'  # Prevent caching issues
            )

            # Generate presigned URL
            expiry_seconds = expiry_days * 24 * 3600
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiry_seconds
            )

            logger.info(f"Uploaded breakdown to R2: {key} (expires in {expiry_days} days)")
            return url

        except Exception as e:
            logger.error(f"Failed to upload to R2: {e}")
            return None

    def upload_json(
        self,
        data: dict,
        expiry_days: Optional[int] = None,
        prefix: str = "data"
    ) -> Optional[str]:
        """Upload JSON data to R2 and return presigned URL.

        Args:
            data: Dictionary to serialize as JSON
            expiry_days: Days until URL expires
            prefix: Key prefix/folder in bucket

        Returns:
            Presigned URL string, or None if upload fails
        """
        import json

        is_configured, error = self.is_configured()
        if not is_configured:
            logger.warning(f"R2 not configured: {error}")
            return None

        if expiry_days is None:
            expiry_days = self.default_expiry_days

        try:
            client = self._get_client()

            timestamp = datetime.now().strftime("%Y%m%d")
            unique_id = uuid.uuid4()
            key = f"{prefix}/{timestamp}/{unique_id}.json"

            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(data).encode('utf-8'),
                ContentType='application/json'
            )

            expiry_seconds = expiry_days * 24 * 3600
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiry_seconds
            )

            logger.info(f"Uploaded JSON to R2: {key}")
            return url

        except Exception as e:
            logger.error(f"Failed to upload JSON to R2: {e}")
            return None


# Module-level convenience function
def upload_member_breakdown_html(html_content: str, expiry_days: int = 14) -> Optional[str]:
    """Upload member breakdown HTML and return presigned URL.

    Args:
        html_content: HTML string to upload
        expiry_days: Days until URL expires

    Returns:
        Presigned URL string, or None if R2 not configured or upload fails
    """
    service = R2StorageService()
    return service.upload_html(html_content, expiry_days, prefix="breakdowns")


if __name__ == "__main__":
    # Test configuration
    from dotenv import load_dotenv
    load_dotenv()

    service = R2StorageService()
    is_configured, error = service.is_configured()

    if is_configured:
        print("R2 is configured!")
        print(f"  Endpoint: {service.endpoint}")
        print(f"  Bucket: {service.bucket}")
        print(f"  Default expiry: {service.default_expiry_days} days")

        # Test upload
        test_html = "<html><body><h1>Test</h1><p>This is a test upload.</p></body></html>"
        url = service.upload_html(test_html, expiry_days=1)
        if url:
            print(f"\nTest upload successful!")
            print(f"URL: {url}")
        else:
            print("\nTest upload failed.")
    else:
        print(f"R2 not configured: {error}")
        print("\nRequired environment variables:")
        print("  R2_ACCOUNT_ID")
        print("  R2_ACCESS_KEY_ID")
        print("  R2_SECRET_ACCESS_KEY")
        print("  R2_BUCKET (optional, defaults to 'ichra-shared')")
