"""
Email Service for Canopy
Handles sending PowerPoint proposals via SendGrid with attachment support.

Features:
- SendGrid API integration
- File attachment support (up to 25MB)
- Email validation (RFC 5322)
- Failure notifications to monitoring address
- Structured response handling
"""

import os
import re
import base64
import logging
from datetime import datetime
from html import escape as html_escape
from typing import Optional, Tuple
from dataclasses import dataclass, field
from io import BytesIO

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_ATTACHMENT_SIZE_MB = 25
MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024  # 25MB in bytes

# RFC 5322 compliant email regex pattern
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


@dataclass
class EmailConfig:
    """Configuration for email service."""
    sendgrid_api_key: str = ""
    monitoring_email: str = ""
    sender_email: str = "noreply@glovesolutions.com"
    sender_name: str = "Glove Benefits"

    @classmethod
    def from_environment(cls) -> "EmailConfig":
        """Load configuration from environment variables."""
        return cls(
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            monitoring_email=os.getenv("MONITORING_EMAIL", ""),
            sender_email=os.getenv("SENDER_EMAIL", "noreply@glovesolutions.com"),
            sender_name=os.getenv("SENDER_NAME", "Glove Benefits"),
        )

    def validate(self) -> Tuple[bool, str]:
        """Validate configuration. Returns (is_valid, error_message)."""
        if not self.sendgrid_api_key:
            return False, "SENDGRID_API_KEY environment variable is not set"
        if not self.sendgrid_api_key.startswith("SG."):
            return False, "SENDGRID_API_KEY appears invalid (should start with 'SG.')"
        return True, ""


@dataclass
class EmailResult:
    """Result of an email send operation."""
    success: bool
    recipient: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_details: Optional[dict] = field(default_factory=dict)
    status_code: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "recipient": self.recipient,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "status_code": self.status_code,
        }


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address format (RFC 5322 compliant).

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email address is required"

    email = email.strip()

    # Check for multiple recipients (comma or semicolon separated)
    if "," in email or ";" in email:
        return False, "Only a single recipient email address is allowed"

    # Check length
    if len(email) > 254:
        return False, "Email address is too long (max 254 characters)"

    # Check format with RFC 5322 regex
    if not EMAIL_REGEX.match(email):
        return False, "Invalid email address format"

    # Check for valid domain (at least one dot after @)
    local, domain = email.rsplit("@", 1)
    if "." not in domain:
        return False, "Invalid email domain"

    return True, ""


def validate_file_size(file_data: bytes | BytesIO, filename: str = "") -> Tuple[bool, str]:
    """
    Validate file size is within 25MB limit.

    Args:
        file_data: File data as bytes or BytesIO
        filename: Optional filename for error message

    Returns:
        Tuple of (is_valid, error_message)
    """
    if isinstance(file_data, BytesIO):
        size = len(file_data.getvalue())
    else:
        size = len(file_data)

    if size > MAX_ATTACHMENT_SIZE_BYTES:
        size_mb = size / (1024 * 1024)
        return False, (
            f"File size ({size_mb:.1f}MB) exceeds the {MAX_ATTACHMENT_SIZE_MB}MB email attachment limit. "
            f"Please download the file manually instead."
        )

    return True, ""


class EmailService:
    """
    Email service for sending proposals via SendGrid.

    Usage:
        service = EmailService()
        if service.is_configured():
            result = service.send_proposal_email(
                recipient_email="client@example.com",
                client_name="ABC Company",
                attachment_data=pptx_bytes,
                attachment_filename="proposal.pptx"
            )
    """

    def __init__(self, config: Optional[EmailConfig] = None):
        """Initialize email service with optional config."""
        self.config = config or EmailConfig.from_environment()
        self._sg_client = None

    def is_configured(self) -> Tuple[bool, str]:
        """Check if email service is properly configured."""
        return self.config.validate()

    def _get_sendgrid_client(self):
        """Get or create SendGrid client (lazy initialization)."""
        if self._sg_client is None:
            try:
                from sendgrid import SendGridAPIClient
                self._sg_client = SendGridAPIClient(self.config.sendgrid_api_key)
            except ImportError:
                raise ImportError(
                    "SendGrid package not installed. Run: pip install sendgrid"
                )
        return self._sg_client

    def _create_presentation_email_content(
        self,
        client_name: str,
        attachment_filename: str
    ) -> Tuple[str, str, str]:
        """
        Create email content for presentation delivery.

        Returns:
            Tuple of (subject, plain_text_body, html_body)
        """
        subject = f"ICHRA Proposal for {client_name}"

        plain_text = f"""
Glove Benefits - ICHRA Proposal

Dear {client_name},

Please find attached your ICHRA (Individual Coverage Health Reimbursement Arrangement) proposal.

This proposal outlines the potential benefits and cost savings of transitioning to an ICHRA for your organization.

If you have any questions about this proposal, please don't hesitate to reach out.

Best regards,
Glove Benefits Team

---
This is an automated message. Please do not reply to this email.
"""

        # Escape user-provided values for HTML context
        safe_client_name = html_escape(client_name)

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1e3a5f; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Glove Benefits</h1>
            <p>ICHRA Proposal</p>
        </div>
        <div class="content">
            <p>Dear {safe_client_name},</p>
            <p>Please find attached your <strong>ICHRA (Individual Coverage Health Reimbursement Arrangement) proposal</strong>.</p>
            <p>This proposal outlines the potential benefits and cost savings of transitioning to an ICHRA for your organization.</p>
            <p>If you have any questions about this proposal, please don't hesitate to reach out.</p>
            <p>Best regards,<br><strong>Glove Benefits Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

        return subject, plain_text.strip(), html_body

    def _create_failure_notification_content(
        self,
        recipient_email: str,
        client_name: str,
        presentation_id: str,
        error_details: dict,
        timestamp: datetime
    ) -> Tuple[str, str, str]:
        """
        Create email content for failure notification.

        Returns:
            Tuple of (subject, plain_text_body, html_body)
        """
        subject = f"[ALERT] Proposal Email Delivery Failed - {client_name}"

        error_msg = error_details.get("message", "Unknown error")
        status_code = error_details.get("status_code", "N/A")

        plain_text = f"""
PROPOSAL EMAIL DELIVERY FAILURE

Timestamp: {timestamp.isoformat()}
Client: {client_name}
Intended Recipient: {recipient_email}
Presentation ID: {presentation_id}

Error Details:
- Status Code: {status_code}
- Message: {error_msg}

Please investigate and manually send the proposal if needed.

---
Glove Benefits Monitoring System
"""

        # Escape user-provided values for HTML context
        safe_client_name = html_escape(client_name)
        safe_recipient_email = html_escape(recipient_email)
        safe_presentation_id = html_escape(presentation_id)
        safe_error_msg = html_escape(str(error_msg))
        safe_status_code = html_escape(str(status_code))

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #fef2f2; }}
        .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Proposal Email Delivery Failed</h1>
        </div>
        <div class="content">
            <div class="details">
                <p><strong>Timestamp:</strong> {timestamp.isoformat()}</p>
                <p><strong>Client:</strong> {safe_client_name}</p>
                <p><strong>Intended Recipient:</strong> <code>{safe_recipient_email}</code></p>
                <p><strong>Presentation ID:</strong> <code>{safe_presentation_id}</code></p>
            </div>
            <h3>Error Details</h3>
            <div class="details">
                <p><strong>Status Code:</strong> {safe_status_code}</p>
                <p><strong>Message:</strong> {safe_error_msg}</p>
            </div>
            <p>Please investigate and manually send the proposal if needed.</p>
        </div>
        <div class="footer">
            <p>Glove Benefits Monitoring System</p>
        </div>
    </div>
</body>
</html>
"""

        return subject, plain_text.strip(), html_body

    def send_proposal_email(
        self,
        recipient_email: str,
        client_name: str,
        attachment_data: bytes | BytesIO,
        attachment_filename: str,
        presentation_id: Optional[str] = None
    ) -> EmailResult:
        """
        Send proposal email with PowerPoint attachment.

        Args:
            recipient_email: Recipient's email address
            client_name: Client/company name for personalization
            attachment_data: PowerPoint file data (bytes or BytesIO)
            attachment_filename: Filename for the attachment
            presentation_id: Optional unique ID for tracking

        Returns:
            EmailResult with success/failure details
        """
        # Validate configuration
        is_valid, error_msg = self.is_configured()
        if not is_valid:
            return EmailResult(
                success=False,
                recipient=recipient_email,
                error_message=f"Email service not configured: {error_msg}",
            )

        # Validate email
        is_valid, error_msg = validate_email(recipient_email)
        if not is_valid:
            return EmailResult(
                success=False,
                recipient=recipient_email,
                error_message=error_msg,
            )

        # Validate file size
        is_valid, error_msg = validate_file_size(attachment_data, attachment_filename)
        if not is_valid:
            return EmailResult(
                success=False,
                recipient=recipient_email,
                error_message=error_msg,
            )

        # Convert BytesIO to bytes if needed
        if isinstance(attachment_data, BytesIO):
            file_bytes = attachment_data.getvalue()
        else:
            file_bytes = attachment_data

        # Create email content
        subject, plain_text, html_body = self._create_presentation_email_content(
            client_name, attachment_filename
        )

        try:
            from sendgrid.helpers.mail import (
                Mail, Attachment, FileContent, FileName,
                FileType, Disposition
            )

            # Create message
            message = Mail(
                from_email=(self.config.sender_email, self.config.sender_name),
                to_emails=recipient_email,
                subject=subject,
                plain_text_content=plain_text,
                html_content=html_body
            )

            # Add attachment
            encoded_file = base64.b64encode(file_bytes).decode()

            # Determine MIME type
            if attachment_filename.endswith('.pdf'):
                mime_type = 'application/pdf'
            else:
                mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'

            attachment = Attachment(
                FileContent(encoded_file),
                FileName(attachment_filename),
                FileType(mime_type),
                Disposition('attachment')
            )
            message.attachment = attachment

            # Send email
            sg = self._get_sendgrid_client()
            response = sg.send(message)

            # Check response
            if response.status_code in (200, 201, 202):
                return EmailResult(
                    success=True,
                    recipient=recipient_email,
                    sent_at=datetime.now(),
                    status_code=response.status_code,
                )
            else:
                error_details = {
                    "status_code": response.status_code,
                    "message": f"SendGrid returned status {response.status_code}",
                    "body": response.body.decode() if response.body else "",
                }

                # Send failure notification
                self._send_failure_notification(
                    recipient_email=recipient_email,
                    client_name=client_name,
                    presentation_id=presentation_id or attachment_filename,
                    error_details=error_details,
                )

                return EmailResult(
                    success=False,
                    recipient=recipient_email,
                    error_message=f"SendGrid returned status {response.status_code}",
                    error_details=error_details,
                    status_code=response.status_code,
                )

        except Exception as e:
            error_details = {
                "status_code": None,
                "message": str(e),
                "exception_type": type(e).__name__,
            }

            # Send failure notification
            self._send_failure_notification(
                recipient_email=recipient_email,
                client_name=client_name,
                presentation_id=presentation_id or attachment_filename,
                error_details=error_details,
            )

            logger.exception("Failed to send proposal email")
            return EmailResult(
                success=False,
                recipient=recipient_email,
                error_message=f"Failed to send email: {str(e)}",
                error_details=error_details,
            )

    def _send_failure_notification(
        self,
        recipient_email: str,
        client_name: str,
        presentation_id: str,
        error_details: dict
    ) -> None:
        """
        Send failure notification to monitoring email address.

        This method silently fails if notification cannot be sent,
        to prevent infinite loops.
        """
        if not self.config.monitoring_email:
            logger.warning("No monitoring email configured, skipping failure notification")
            return

        try:
            from sendgrid.helpers.mail import Mail

            timestamp = datetime.now()
            subject, plain_text, html_body = self._create_failure_notification_content(
                recipient_email=recipient_email,
                client_name=client_name,
                presentation_id=presentation_id,
                error_details=error_details,
                timestamp=timestamp,
            )

            message = Mail(
                from_email=(self.config.sender_email, self.config.sender_name),
                to_emails=self.config.monitoring_email,
                subject=subject,
                plain_text_content=plain_text,
                html_content=html_body
            )

            sg = self._get_sendgrid_client()
            sg.send(message)

            logger.info(f"Failure notification sent to {self.config.monitoring_email}")

        except Exception as e:
            # Log but don't raise - prevent infinite loops
            logger.error(f"Failed to send failure notification: {e}")


# Convenience function for Streamlit usage
def get_email_service() -> EmailService:
    """Get configured email service instance."""
    return EmailService()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Email Service for Canopy")
    parser.add_argument(
        "--test",
        metavar="EMAIL",
        help="Send a test email to the specified address"
    )
    args = parser.parse_args()

    print("Email Service - Canopy")
    print("=" * 50)

    # Check configuration
    print("\n1. Configuration Check")
    print("-" * 30)
    service = EmailService()
    is_configured, msg = service.is_configured()

    if is_configured:
        print("  ✓ SENDGRID_API_KEY is set")
        if service.config.monitoring_email:
            print(f"  ✓ MONITORING_EMAIL: {service.config.monitoring_email}")
        else:
            print("  - MONITORING_EMAIL: not set (optional)")
        print(f"  - Sender: {service.config.sender_name} <{service.config.sender_email}>")
    else:
        print(f"  ✗ {msg}")

    # Email validation tests
    print("\n2. Email Validation Tests")
    print("-" * 30)
    test_emails = [
        ("valid@example.com", True),
        ("user.name@domain.org", True),
        ("invalid", False),
        ("no@domain", False),
    ]

    for email, expected in test_emails:
        is_valid, err = validate_email(email)
        status = "✓" if is_valid == expected else "✗"
        print(f"  {status} {email!r:30} -> {'valid' if is_valid else 'invalid'}")

    # Send test email if requested
    if args.test:
        print(f"\n3. Sending Test Email")
        print("-" * 30)
        print(f"  Recipient: {args.test}")

        # Validate recipient
        is_valid, err = validate_email(args.test)
        if not is_valid:
            print(f"  ✗ Invalid email: {err}")
            exit(1)

        if not is_configured:
            print("  ✗ Cannot send: email service not configured")
            exit(1)

        # Create a simple test attachment (small text file as PDF simulation)
        test_content = f"""
Canopy - Email Service Test

This is a test email sent at: {datetime.now().isoformat()}

If you received this email with attachment, the SendGrid integration is working correctly.

Configuration:
- Sender: {service.config.sender_name} <{service.config.sender_email}>
- Monitoring: {service.config.monitoring_email or 'not configured'}
""".encode('utf-8')

        print("  Sending...")
        result = service.send_proposal_email(
            recipient_email=args.test,
            client_name="Test Client",
            attachment_data=test_content,
            attachment_filename="email_service_test.txt",
            presentation_id="test_" + datetime.now().strftime('%Y%m%d_%H%M%S')
        )

        if result.success:
            print(f"  ✓ Email sent successfully!")
            print(f"    Sent at: {result.sent_at}")
            print(f"    Status code: {result.status_code}")
        else:
            print(f"  ✗ Failed to send email")
            print(f"    Error: {result.error_message}")
            if result.error_details:
                print(f"    Details: {result.error_details}")
            exit(1)
    else:
        print("\n3. Send Test Email")
        print("-" * 30)
        print("  To send a test email, run:")
        print("  python email_service.py --test your@email.com")

    print("\n" + "=" * 50)
    print("Done!")
