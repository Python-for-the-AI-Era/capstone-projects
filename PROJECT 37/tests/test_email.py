"""
Tests for email service.

This module tests email functionality including SMTP configuration,
attachment handling, and error scenarios.
"""

from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from typing import List

import pytest
import smtplib

from pipeline_pkg.services.email import EmailSender
from pipeline_pkg.models import EmailLog


class TestEmailSender:
    """Test cases for EmailSender."""
    
    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.sender = EmailSender(
            smtp_server="smtp.example.com",
            smtp_port=587,
            username="test@example.com",
            password="password123",
            use_tls=True,
        )
    
    def test_initialization(self) -> None:
        """Test EmailSender initialization."""
        assert self.sender.smtp_server == "smtp.example.com"
        assert self.sender.smtp_port == 587
        assert self.sender.username == "test@example.com"
        assert self.sender.password == "password123"
        assert self.sender.use_tls is True
        assert self.sender._smtp_client is None
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_connect_success(self, mock_smtp: Mock) -> None:
        """Test successful SMTP connection."""
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        client = self.sender._connect()
        
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_client.starttls.assert_called_once()
        mock_client.login.assert_called_once_with("test@example.com", "password123")
        assert client == mock_client
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_connect_no_tls(self, mock_smtp: Mock) -> None:
        """Test SMTP connection without TLS."""
        sender = EmailSender(
            smtp_server="smtp.example.com",
            smtp_port=25,
            username="test@example.com",
            password="password123",
            use_tls=False,
        )
        
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        sender._connect()
        
        mock_client.starttls.assert_not_called()
        mock_client.login.assert_called_once_with("test@example.com", "password123")
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_connect_failure(self, mock_smtp: Mock) -> None:
        """Test SMTP connection failure."""
        mock_smtp.side_effect = smtplib.SMTPException("Connection failed")
        
        with pytest.raises(smtplib.SMTPException):
            self.sender._connect()
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_disconnect_success(self, mock_smtp: Mock) -> None:
        """Test successful SMTP disconnection."""
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        self.sender._disconnect(mock_client)
        
        mock_client.quit.assert_called_once()
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_disconnect_failure(self, mock_smtp: Mock) -> None:
        """Test SMTP disconnection failure."""
        mock_client = Mock()
        mock_client.quit.side_effect = Exception("Disconnect failed")
        mock_smtp.return_value = mock_client
        
        # Should not raise exception
        self.sender._disconnect(mock_client)
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    def test_create_message_no_attachments(self, mock_smtp: Mock) -> None:
        """Test creating message without attachments."""
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        msg = self.sender._create_message(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        
        assert msg["From"] == "test@example.com"
        assert msg["To"] == "test@example.com"
        assert msg["Subject"] == "Test Subject"
        assert len(msg.get_payload()) == 1  # Only body part
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("builtins.open", new_callable=mock_open, read_data=b"file content")
    @patch("pathlib.Path.exists")
    def test_create_message_with_attachments(self, mock_exists: Mock, mock_file: Mock, mock_smtp: Mock) -> None:
        """Test creating message with attachments."""
        mock_exists.return_value = True
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        attachments = ["/path/to/file1.txt", "/path/to/file2.pdf"]
        
        msg = self.sender._create_message(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
            attachments=attachments,
        )
        
        # Should have body + 2 attachments
        assert len(msg.get_payload()) == 3
        
        # Check attachment parts
        attachment_parts = [
            part for part in msg.get_payload() 
            if part.get_content_disposition() and "attachment" in part.get_content_disposition()
        ]
        assert len(attachment_parts) == 2
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("builtins.open", new_callable=mock_open, read_data=b"file content")
    @patch("pathlib.Path.exists")
    def test_create_message_missing_attachment(self, mock_exists: Mock, mock_file: Mock, mock_smtp: Mock) -> None:
        """Test creating message with missing attachment."""
        mock_exists.return_value = False
        mock_client = Mock()
        mock_smtp.return_value = mock_client
        
        attachments = ["/path/to/missing.txt"]
        
        msg = self.sender._create_message(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
            attachments=attachments,
        )
        
        # Should only have body part (attachment missing)
        assert len(msg.get_payload()) == 1
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_send_email_success(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test successful email sending."""
        mock_client = Mock()
        mock_connect.return_value = mock_client
        
        log = self.sender.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        
        mock_connect.assert_called_once()
        mock_client.send_message.assert_called_once()
        mock_disconnect.assert_called_once_with(mock_client)
        
        assert log.recipient == "test@example.com"
        assert log.subject == "Test Subject"
        assert log.status == "sent"
        assert log.error_message is None
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_send_email_with_attachments(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test sending email with attachments."""
        mock_client = Mock()
        mock_connect.return_value = mock_client
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"file content")):
            
            log = self.sender.send_email(
                recipient="test@example.com",
                subject="Test Subject",
                body="Test body",
                attachments=["/path/to/file.txt"],
            )
        
        assert log.status == "sent"
        mock_client.send_message.assert_called_once()
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_send_email_failure(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test email sending failure."""
        mock_client = Mock()
        mock_connect.return_value = mock_client
        mock_client.send_message.side_effect = smtplib.SMTPException("Send failed")
        
        log = self.sender.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        
        mock_connect.assert_called_once()
        mock_disconnect.assert_called_once_with(mock_client)
        
        assert log.status == "failed"
        assert log.error_message == "Send failed"
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_send_email_connection_failure(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test email sending with connection failure."""
        mock_connect.side_effect = smtplib.SMTPException("Connection failed")
        
        log = self.sender.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        
        mock_connect.assert_called_once()
        mock_disconnect.assert_not_called()
        
        assert log.status == "failed"
        assert log.error_message == "Connection failed"
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender.send_email")
    def test_send_bulk_emails(self, mock_send_email: Mock, mock_smtp: Mock) -> None:
        """Test sending bulk emails."""
        # Mock successful sends
        mock_send_email.side_effect = [
            EmailLog(recipient="user1@example.com", subject="Test", status="sent"),
            EmailLog(recipient="user2@example.com", subject="Test", status="sent"),
            EmailLog(recipient="user3@example.com", subject="Test", status="failed", error_message="Failed"),
        ]
        
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        results = self.sender.send_bulk_emails(
            recipients=recipients,
            subject="Test Subject",
            body="Test body",
        )
        
        assert len(results) == 3
        assert mock_send_email.call_count == 3
        
        # Check results
        assert results[0].status == "sent"
        assert results[1].status == "sent"
        assert results[2].status == "failed"
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_test_connection_success(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test successful connection test."""
        mock_client = Mock()
        mock_connect.return_value = mock_client
        
        result = self.sender.test_connection()
        
        assert result is True
        mock_connect.assert_called_once()
        mock_disconnect.assert_called_once_with(mock_client)
    
    @patch("pipeline_pkg.services.email.smtplib.SMTP")
    @patch("pipeline_pkg.services.email.EmailSender._connect")
    @patch("pipeline_pkg.services.email.EmailSender._disconnect")
    def test_test_connection_failure(self, mock_disconnect: Mock, mock_connect: Mock, mock_smtp: Mock) -> None:
        """Test failed connection test."""
        mock_connect.side_effect = smtplib.SMTPException("Connection failed")
        
        result = self.sender.test_connection()
        
        assert result is False
        mock_connect.assert_called_once()
        mock_disconnect.assert_not_called()
    
    def test_context_manager(self) -> None:
        """Test EmailSender as context manager."""
        with EmailSender(
            smtp_server="smtp.example.com",
            smtp_port=587,
            username="test@example.com",
            password="password123",
        ) as sender:
            assert sender.smtp_server == "smtp.example.com"
            assert sender.username == "test@example.com"
