"""
URL Shortener Service

Uses dub.co API to create short links for QR codes.
"""

import os
import logging
from typing import Optional

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class DubShortener:
    """URL shortener using dub.co API."""

    API_URL = "https://api.dub.co/links"

    def __init__(self):
        self.api_key = os.getenv('DUB_API_KEY')

    def is_configured(self) -> tuple[bool, Optional[str]]:
        """Check if dub.co is configured."""
        if not self.api_key:
            return False, "DUB_API_KEY not set"
        return True, None

    def shorten(self, url: str, tag: str = None) -> Optional[str]:
        """Shorten a URL using dub.co.

        Args:
            url: The long URL to shorten
            tag: Optional tag for organization (e.g., "qr-codes")

        Returns:
            Short URL string, or None if shortening fails
        """
        is_configured, error = self.is_configured()
        if not is_configured:
            logger.debug(f"Dub not configured: {error}")
            return None

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "url": url,
            }
            if tag:
                payload["tagIds"] = [tag]

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                short_url = data.get('shortLink')
                logger.info(f"Shortened URL: {url[:50]}... -> {short_url}")
                return short_url
            else:
                logger.warning(f"Dub API error {response.status_code}: {response.text}")
                return None

        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to shorten URL: {e}")
            return None


def shorten_url(url: str) -> str:
    """Convenience function to shorten a URL.

    Returns the short URL if successful, otherwise returns the original URL.
    """
    shortener = DubShortener()
    short = shortener.shorten(url)
    return short if short else url


if __name__ == "__main__":
    # Test URL shortening
    test_url = "https://example.com/very/long/path/to/member/breakdown?id=12345"

    shortener = DubShortener()
    is_configured, error = shortener.is_configured()

    if is_configured:
        print("Testing dub.co URL shortening...")
        short = shortener.shorten(test_url)
        if short:
            print(f"Original: {test_url}")
            print(f"Short:    {short}")
        else:
            print("Shortening failed")
    else:
        print(f"Dub not configured: {error}")
