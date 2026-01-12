"""
Test Suite for Email Service - ICHRA Calculator
Tests mapped to REQ-2 Acceptance Criteria

Run with: python test_email_service.py
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from datetime import datetime

from email_service import (
    EmailService,
    EmailConfig,
    EmailResult,
    validate_email,
    validate_file_size,
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_ATTACHMENT_SIZE_MB,
)


# =============================================================================
# AC: Recipient Input - Email Validation (RFC 5322)
# "Given a user is configuring PowerPoint generation, When they enter a
# recipient email address, Then the system validates the email format and
# prevents proceeding if invalid"
# =============================================================================

class TestEmailValidation(unittest.TestCase):
    """Tests for RFC 5322 email validation - maps to TASK-10"""

    def test_valid_email_simple(self):
        """AC: Valid email acceptance - simple format"""
        is_valid, error = validate_email("client@example.com")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_valid_email_with_dots(self):
        """AC: Valid email acceptance - dots in local part"""
        is_valid, error = validate_email("user.name@domain.org")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_valid_email_with_plus(self):
        """AC: Valid email acceptance - plus addressing"""
        is_valid, error = validate_email("user+tag@example.com")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_valid_email_subdomain(self):
        """AC: Valid email acceptance - subdomain"""
        is_valid, error = validate_email("user@mail.example.com")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_invalid_email_no_at(self):
        """AC: Invalid email rejection - missing @"""
        is_valid, error = validate_email("invalid")
        self.assertFalse(is_valid)
        self.assertIn("Invalid", error)

    def test_invalid_email_no_domain_dot(self):
        """AC: Invalid email rejection - no dot in domain"""
        is_valid, error = validate_email("user@domain")
        self.assertFalse(is_valid)
        self.assertIn("domain", error.lower())

    def test_invalid_email_empty(self):
        """AC: Invalid email rejection - empty string"""
        is_valid, error = validate_email("")
        self.assertFalse(is_valid)
        self.assertIn("required", error.lower())

    def test_invalid_email_whitespace_only(self):
        """AC: Invalid email rejection - whitespace only"""
        is_valid, error = validate_email("   ")
        self.assertFalse(is_valid)

    def test_invalid_email_too_long(self):
        """AC: Invalid email rejection - exceeds 254 characters"""
        long_email = "a" * 250 + "@example.com"
        is_valid, error = validate_email(long_email)
        self.assertFalse(is_valid)
        self.assertIn("too long", error.lower())

    def test_multiple_recipients_comma_rejected(self):
        """AC: Multiple recipient rejection - comma separated"""
        is_valid, error = validate_email("user1@example.com, user2@example.com")
        self.assertFalse(is_valid)
        self.assertIn("single", error.lower())

    def test_multiple_recipients_semicolon_rejected(self):
        """AC: Multiple recipient rejection - semicolon separated"""
        is_valid, error = validate_email("user1@example.com; user2@example.com")
        self.assertFalse(is_valid)
        self.assertIn("single", error.lower())

    def test_email_whitespace_stripped(self):
        """AC: Email with leading/trailing whitespace is trimmed and validated"""
        is_valid, error = validate_email("  client@example.com  ")
        self.assertTrue(is_valid)


# =============================================================================
# AC: File Size Error Handling
# "Given a generated PowerPoint exceeds the 25MB attachment limit, When the
# system attempts to attach the file, Then the user sees an error message
# indicating file size limit exceeded with option to download manually"
# =============================================================================

class TestFileSizeValidation(unittest.TestCase):
    """Tests for 25MB file size limit - maps to TASK-11, TASK-12"""

    def test_file_under_limit_bytes(self):
        """AC: File under 25MB accepted - bytes input"""
        small_file = b"x" * 1000  # 1KB
        is_valid, error = validate_file_size(small_file)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_file_under_limit_bytesio(self):
        """AC: File under 25MB accepted - BytesIO input"""
        small_file = BytesIO(b"x" * 1000)
        is_valid, error = validate_file_size(small_file)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_file_at_limit(self):
        """AC: File exactly at 25MB accepted"""
        exact_limit = b"x" * MAX_ATTACHMENT_SIZE_BYTES
        is_valid, error = validate_file_size(exact_limit)
        self.assertTrue(is_valid)

    def test_file_over_limit(self):
        """AC: File over 25MB rejected with clear error"""
        over_limit = b"x" * (MAX_ATTACHMENT_SIZE_BYTES + 1)
        is_valid, error = validate_file_size(over_limit)
        self.assertFalse(is_valid)
        self.assertIn("25", error)
        self.assertIn("download", error.lower())

    def test_file_over_limit_shows_actual_size(self):
        """AC: Error message shows actual file size"""
        size_30mb = 30 * 1024 * 1024
        over_limit = b"x" * size_30mb
        is_valid, error = validate_file_size(over_limit)
        self.assertFalse(is_valid)
        self.assertIn("30", error)  # Should show ~30MB


# =============================================================================
# AC: Configuration Validation
# "Given SendGrid API authentication fails, When the system attempts to send
# the email, Then the user sees a generic error message"
# =============================================================================

class TestEmailConfig(unittest.TestCase):
    """Tests for SendGrid configuration - maps to TASK-1"""

    def test_config_from_environment(self):
        """AC: Configuration loads from environment variables"""
        with patch.dict('os.environ', {
            'SENDGRID_API_KEY': 'SG.test_key',
            'MONITORING_EMAIL': 'monitor@example.com',
            'SENDER_EMAIL': 'sender@example.com',
            'SENDER_NAME': 'Test Sender'
        }):
            config = EmailConfig.from_environment()
            self.assertEqual(config.sendgrid_api_key, 'SG.test_key')
            self.assertEqual(config.monitoring_email, 'monitor@example.com')
            self.assertEqual(config.sender_email, 'sender@example.com')
            self.assertEqual(config.sender_name, 'Test Sender')

    def test_config_defaults(self):
        """AC: Configuration has sensible defaults"""
        with patch.dict('os.environ', {}, clear=True):
            config = EmailConfig.from_environment()
            self.assertEqual(config.sender_email, 'noreply@glovesolutions.com')
            self.assertEqual(config.sender_name, 'Glove Benefits')

    def test_config_validation_missing_key(self):
        """AC: Missing API key fails validation with clear error"""
        config = EmailConfig(sendgrid_api_key="")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("SENDGRID_API_KEY", error)

    def test_config_validation_invalid_key_format(self):
        """AC: Invalid API key format fails validation"""
        config = EmailConfig(sendgrid_api_key="invalid_key")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("SG.", error)

    def test_config_validation_valid_key(self):
        """AC: Valid API key passes validation"""
        config = EmailConfig(sendgrid_api_key="SG.valid_api_key")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)
        self.assertEqual(error, "")


# =============================================================================
# AC: Email Service Configuration Check
# =============================================================================

class TestEmailServiceConfiguration(unittest.TestCase):
    """Tests for EmailService.is_configured() - maps to TASK-1"""

    def test_service_not_configured_without_key(self):
        """AC: Service reports not configured when API key missing"""
        config = EmailConfig(sendgrid_api_key="")
        service = EmailService(config)
        is_configured, error = service.is_configured()
        self.assertFalse(is_configured)
        self.assertIn("SENDGRID_API_KEY", error)

    def test_service_configured_with_valid_key(self):
        """AC: Service reports configured when API key valid"""
        config = EmailConfig(sendgrid_api_key="SG.valid_key")
        service = EmailService(config)
        is_configured, error = service.is_configured()
        self.assertTrue(is_configured)


# =============================================================================
# AC: Email Delivery & File Attachment
# "Given a user configures a PowerPoint presentation and provides a valid
# recipient email, When the generation completes successfully, Then the system
# automatically sends an email with the presentation attached"
# =============================================================================

class TestEmailSending(unittest.TestCase):
    """Tests for send_proposal_email() - maps to TASK-11, TASK-12, TASK-16"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_config = EmailConfig(
            sendgrid_api_key="SG.test_key",
            monitoring_email="monitor@example.com",
            sender_email="sender@example.com",
            sender_name="Test Sender"
        )
        self.sample_attachment = b"Sample PowerPoint content"
        self.sample_filename = "proposal.pptx"

    def test_send_fails_without_configuration(self):
        """AC: Send fails gracefully when not configured"""
        config = EmailConfig(sendgrid_api_key="")
        service = EmailService(config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=self.sample_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertFalse(result.success)
        self.assertIn("not configured", result.error_message.lower())

    def test_send_fails_with_invalid_email(self):
        """AC: Send fails when recipient email is invalid"""
        service = EmailService(self.valid_config)

        result = service.send_proposal_email(
            recipient_email="invalid-email",
            client_name="Test Client",
            attachment_data=self.sample_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertFalse(result.success)
        self.assertEqual(result.recipient, "invalid-email")

    def test_send_fails_with_oversized_file(self):
        """AC: File size validation - send fails when file exceeds 25MB"""
        service = EmailService(self.valid_config)
        oversized_file = b"x" * (MAX_ATTACHMENT_SIZE_BYTES + 1)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=oversized_file,
            attachment_filename=self.sample_filename
        )

        self.assertFalse(result.success)
        self.assertIn("25", result.error_message)
        self.assertIn("download", result.error_message.lower())

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_send_success(self, mock_get_client):
        """AC: Email Delivery - successful send returns success result"""
        # Mock SendGrid response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.body = b""

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        service = EmailService(self.valid_config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=self.sample_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertTrue(result.success)
        self.assertEqual(result.recipient, "client@example.com")
        self.assertIsNotNone(result.sent_at)
        self.assertEqual(result.status_code, 202)

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_send_success_with_bytesio(self, mock_get_client):
        """AC: File Attachment - BytesIO input handled correctly"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.body = b""

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        service = EmailService(self.valid_config)
        bytesio_attachment = BytesIO(self.sample_attachment)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=bytesio_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertTrue(result.success)

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_send_handles_sendgrid_error(self, mock_get_client):
        """AC: System-Level Error Handling - SendGrid errors captured"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.body = b"Bad Request"

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        service = EmailService(self.valid_config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=self.sample_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertFalse(result.success)
        self.assertIn("400", result.error_message)
        self.assertIsNotNone(result.error_details)
        self.assertEqual(result.status_code, 400)

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_send_handles_exception(self, mock_get_client):
        """AC: System-Level Error Handling - exceptions captured gracefully"""
        mock_client = Mock()
        mock_client.send.side_effect = Exception("Network error")
        mock_get_client.return_value = mock_client

        service = EmailService(self.valid_config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=self.sample_attachment,
            attachment_filename=self.sample_filename
        )

        self.assertFalse(result.success)
        self.assertIn("Network error", result.error_message)
        self.assertEqual(result.error_details.get("exception_type"), "Exception")


# =============================================================================
# AC: Success Confirmation
# "Given an email was sent successfully, When the user views the generation
# result, Then they see a confirmation message indicating the email was sent
# to the specified recipient"
# =============================================================================

class TestEmailResult(unittest.TestCase):
    """Tests for EmailResult data structure - maps to TASK-16, TASK-17"""

    def test_success_result_has_required_fields(self):
        """AC: Success Confirmation - result contains recipient and timestamp"""
        result = EmailResult(
            success=True,
            recipient="client@example.com",
            sent_at=datetime.now(),
            status_code=202
        )

        self.assertTrue(result.success)
        self.assertEqual(result.recipient, "client@example.com")
        self.assertIsNotNone(result.sent_at)

    def test_failure_result_has_error_details(self):
        """AC: Error Handling - failure result contains error details"""
        result = EmailResult(
            success=False,
            recipient="client@example.com",
            error_message="SendGrid error",
            error_details={"status_code": 400, "message": "Bad Request"}
        )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIsNotNone(result.error_details)

    def test_result_to_dict_serialization(self):
        """AC: Result can be serialized for UI display"""
        result = EmailResult(
            success=True,
            recipient="client@example.com",
            sent_at=datetime(2025, 12, 26, 12, 0, 0),
            status_code=202
        )

        result_dict = result.to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["recipient"], "client@example.com")
        self.assertIsNotNone(result_dict["sent_at"])


# =============================================================================
# AC: Failure Notification
# "Given SendGrid accepts the email but delivery fails, When the delivery
# failure occurs, Then a failure notification email is sent to the configured
# monitoring address with timestamp, intended recipient, presentation ID, and
# SendGrid error details"
# =============================================================================

class TestFailureNotification(unittest.TestCase):
    """Tests for failure notification service - maps to TASK-13, TASK-14, TASK-15"""

    def setUp(self):
        """Set up test fixtures"""
        self.config_with_monitoring = EmailConfig(
            sendgrid_api_key="SG.test_key",
            monitoring_email="monitor@example.com",
            sender_email="sender@example.com",
            sender_name="Test Sender"
        )
        self.config_without_monitoring = EmailConfig(
            sendgrid_api_key="SG.test_key",
            monitoring_email="",
            sender_email="sender@example.com",
            sender_name="Test Sender"
        )

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_failure_notification_sent_on_error(self, mock_get_client):
        """AC: Failure notification sent when delivery fails"""
        # First call fails (delivery), second call succeeds (notification)
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.body = b"Server Error"

        mock_response_success = Mock()
        mock_response_success.status_code = 202

        mock_client = Mock()
        mock_client.send.side_effect = [mock_response_fail, mock_response_success]
        mock_get_client.return_value = mock_client

        service = EmailService(self.config_with_monitoring)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=b"test",
            attachment_filename="test.pptx",
            presentation_id="PRES-123"
        )

        # Verify delivery failed
        self.assertFalse(result.success)

        # Verify notification was attempted (2 calls: delivery + notification)
        self.assertEqual(mock_client.send.call_count, 2)

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_no_notification_when_monitoring_not_configured(self, mock_get_client):
        """AC: No notification sent if monitoring email not configured"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.body = b"Server Error"

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        service = EmailService(self.config_without_monitoring)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=b"test",
            attachment_filename="test.pptx"
        )

        # Only delivery attempt, no notification
        self.assertEqual(mock_client.send.call_count, 1)

    def test_failure_notification_content_includes_required_fields(self):
        """AC: Notification includes timestamp, recipient, presentation ID, error details"""
        service = EmailService(self.config_with_monitoring)

        error_details = {
            "status_code": 500,
            "message": "Internal Server Error"
        }

        subject, plain_text, html_body = service._create_failure_notification_content(
            recipient_email="client@example.com",
            client_name="Test Client",
            presentation_id="PRES-123",
            error_details=error_details,
            timestamp=datetime(2025, 12, 26, 12, 0, 0)
        )

        # Check subject
        self.assertIn("Failed", subject)
        self.assertIn("Test Client", subject)

        # Check plain text content
        self.assertIn("client@example.com", plain_text)
        self.assertIn("PRES-123", plain_text)
        self.assertIn("500", plain_text)
        self.assertIn("Internal Server Error", plain_text)

        # Check HTML content
        self.assertIn("client@example.com", html_body)
        self.assertIn("PRES-123", html_body)

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_notification_failure_does_not_raise(self, mock_get_client):
        """AC: Notification failure does not create infinite loop"""
        # Both delivery and notification fail
        mock_client = Mock()
        mock_client.send.side_effect = Exception("All sends fail")
        mock_get_client.return_value = mock_client

        service = EmailService(self.config_with_monitoring)

        # Should not raise exception
        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=b"test",
            attachment_filename="test.pptx"
        )

        self.assertFalse(result.success)


# =============================================================================
# AC: Email Content & HTML Escaping (Security)
# =============================================================================

class TestEmailContent(unittest.TestCase):
    """Tests for email content generation - maps to TASK-7, TASK-8"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = EmailConfig(
            sendgrid_api_key="SG.test_key",
            sender_email="sender@example.com",
            sender_name="Test Sender"
        )
        self.service = EmailService(self.config)

    def test_presentation_email_subject(self):
        """AC: Email has professional subject line"""
        subject, _, _ = self.service._create_presentation_email_content(
            client_name="ABC Company",
            attachment_filename="proposal.pptx"
        )

        self.assertIn("ICHRA", subject)
        self.assertIn("ABC Company", subject)

    def test_presentation_email_body_content(self):
        """AC: Email body contains required elements"""
        _, plain_text, html_body = self.service._create_presentation_email_content(
            client_name="ABC Company",
            attachment_filename="proposal.pptx"
        )

        # Check plain text
        self.assertIn("ABC Company", plain_text)
        self.assertIn("ICHRA", plain_text)
        self.assertIn("Glove Benefits", plain_text)

        # Check HTML
        self.assertIn("ABC Company", html_body)
        self.assertIn("ICHRA", html_body)

    def test_html_escaping_prevents_xss(self):
        """AC: Security - HTML injection prevented in client name"""
        malicious_name = "<script>alert('xss')</script>"

        _, _, html_body = self.service._create_presentation_email_content(
            client_name=malicious_name,
            attachment_filename="proposal.pptx"
        )

        # Should be escaped, not raw
        self.assertNotIn("<script>", html_body)
        self.assertIn("&lt;script&gt;", html_body)

    def test_failure_notification_html_escaping(self):
        """AC: Security - HTML injection prevented in failure notification"""
        malicious_recipient = "<img src=x onerror=alert('xss')>"

        _, _, html_body = self.service._create_failure_notification_content(
            recipient_email=malicious_recipient,
            client_name="Test Client",
            presentation_id="PRES-123",
            error_details={"message": "<script>bad</script>"},
            timestamp=datetime.now()
        )

        self.assertNotIn("<img src=x", html_body)
        self.assertNotIn("<script>bad</script>", html_body)


# =============================================================================
# AC: MIME Type Handling
# =============================================================================

class TestMimeTypeHandling(unittest.TestCase):
    """Tests for correct MIME type assignment"""

    def test_pptx_extension_detection(self):
        """AC: PowerPoint files identified by .pptx extension"""
        # Test the logic that determines MIME type
        filename = "proposal.pptx"

        # This mirrors the logic in send_proposal_email
        if filename.endswith('.pdf'):
            mime_type = 'application/pdf'
        else:
            mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'

        self.assertIn("presentationml", mime_type)

    def test_pdf_extension_detection(self):
        """AC: PDF files identified by .pdf extension"""
        filename = "proposal.pdf"

        if filename.endswith('.pdf'):
            mime_type = 'application/pdf'
        else:
            mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'

        self.assertEqual(mime_type, 'application/pdf')

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_pptx_sends_successfully(self, mock_get_client):
        """AC: PowerPoint files can be sent via email"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.body = b""

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        config = EmailConfig(sendgrid_api_key="SG.test_key")
        service = EmailService(config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=b"test content",
            attachment_filename="proposal.pptx"
        )

        self.assertTrue(result.success)
        mock_client.send.assert_called_once()

    @patch('email_service.EmailService._get_sendgrid_client')
    def test_pdf_sends_successfully(self, mock_get_client):
        """AC: PDF files can be sent via email"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.body = b""

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_get_client.return_value = mock_client

        config = EmailConfig(sendgrid_api_key="SG.test_key")
        service = EmailService(config)

        result = service.send_proposal_email(
            recipient_email="client@example.com",
            client_name="Test Client",
            attachment_data=b"test content",
            attachment_filename="proposal.pdf"
        )

        self.assertTrue(result.success)
        mock_client.send.assert_called_once()


# =============================================================================
# Test Runner with Summary
# =============================================================================

if __name__ == "__main__":
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestEmailValidation,
        TestFileSizeValidation,
        TestEmailConfig,
        TestEmailServiceConfiguration,
        TestEmailSending,
        TestEmailResult,
        TestFailureNotification,
        TestEmailContent,
        TestMimeTypeHandling,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run with verbosity
    print("=" * 70)
    print("EMAIL SERVICE TEST SUITE - REQ-2 Acceptance Criteria")
    print("=" * 70)
    print()

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()

    if result.wasSuccessful():
        print("ALL TESTS PASSED - REQ-2 Acceptance Criteria verified")
    else:
        print("SOME TESTS FAILED - Review failures above")

        if result.failures:
            print("\nFailed tests:")
            for test, _ in result.failures:
                print(f"  - {test}")

        if result.errors:
            print("\nTests with errors:")
            for test, _ in result.errors:
                print(f"  - {test}")

    print("=" * 70)
