"""
Email service for sending notifications and reports.

This module provides email functionality with SMTP configuration,
attachment support, and comprehensive logging.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import structlog

from ..models import EmailLog


class EmailSender:
    """
    Email service for sending notifications and reports.
    
    Provides SMTP-based email sending with attachment support
    and comprehensive error handling.
    """
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        """
        Initialize the email sender.
        
        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
            use_tls: Whether to use TLS encryption
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.logger = structlog.get_logger(__name__)
        self._smtp_client: Optional[smtplib.SMTP] = None
    
    def _connect(self) -> smtplib.SMTP:
        """Connect to SMTP server."""
        try:
            smtp_client = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            if self.use_tls:
                smtp_client.starttls()
            
            smtp_client.login(self.username, self.password)
            
            self.logger.info(
                "Connected to SMTP server",
                server=self.smtp_server,
                port=self.smtp_port,
                username=self.username,
            )
            
            return smtp_client
            
        except Exception as e:
            self.logger.error(
                "Failed to connect to SMTP server",
                server=self.smtp_server,
                port=self.smtp_port,
                error=str(e),
            )
            raise
    
    def _disconnect(self, smtp_client: smtplib.SMTP) -> None:
        """Disconnect from SMTP server."""
        try:
            if smtp_client:
                smtp_client.quit()
                self.logger.info("Disconnected from SMTP server")
        except Exception as e:
            self.logger.error("Error disconnecting from SMTP server", error=str(e))
    
    def _create_message(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> MIMEMultipart:
        """
        Create email message with optional attachments.
        
        Args:
            recipient: Email recipient
            subject: Email subject
            body: Email body
            attachments: List of file paths to attach
            
        Returns:
            Configured MIMEMultipart message
        """
        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = recipient
        msg["Subject"] = subject
        
        # Add body
        msg.attach(MIMEText(body, "plain"))
        
        # Add attachments
        if attachments:
            for file_path in attachments:
                path = Path(file_path)
                if path.exists():
                    try:
                        with open(path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=path.name)
                        
                        part[
                            "Content-Disposition"
                        ] = f'attachment; filename="{path.name}"'
                        msg.attach(part)
                        
                        self.logger.debug(
                            "Attachment added",
                            file_path=str(path),
                            size=path.stat().st_size,
                        )
                        
                    except Exception as e:
                        self.logger.warning(
                            "Failed to attach file",
                            file_path=str(path),
                            error=str(e),
                        )
                else:
                    self.logger.warning(
                        "Attachment file not found",
                        file_path=str(path),
                    )
        
        return msg
    
    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> EmailLog:
        """
        Send email with optional attachments.
        
        Args:
            recipient: Email recipient
            subject: Email subject
            body: Email body
            attachments: List of file paths to attach
            
        Returns:
            Email log entry
        """
        log_entry = EmailLog(
            recipient=recipient,
            subject=subject,
            status="pending",
        )
        
        smtp_client = None
        try:
            # Create message
            msg = self._create_message(recipient, subject, body, attachments)
            
            # Connect and send
            smtp_client = self._connect()
            smtp_client.send_message(msg)
            
            log_entry.status = "sent"
            
            self.logger.info(
                "Email sent successfully",
                recipient=recipient,
                subject=subject,
                attachments_count=len(attachments) if attachments else 0,
            )
            
        except Exception as e:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            
            self.logger.error(
                "Failed to send email",
                recipient=recipient,
                subject=subject,
                error=str(e),
            )
            
        finally:
            if smtp_client:
                self._disconnect(smtp_client)
        
        return log_entry
    
    def send_bulk_emails(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> List[EmailLog]:
        """
        Send email to multiple recipients.
        
        Args:
            recipients: List of email recipients
            subject: Email subject
            body: Email body
            attachments: List of file paths to attach
            
        Returns:
            List of email log entries
        """
        results = []
        
        self.logger.info(
            "Starting bulk email send",
            recipient_count=len(recipients),
            subject=subject,
        )
        
        for recipient in recipients:
            try:
                log_entry = self.send_email(recipient, subject, body, attachments)
                results.append(log_entry)
            except Exception as e:
                error_log = EmailLog(
                    recipient=recipient,
                    subject=subject,
                    status="failed",
                    error_message=str(e),
                )
                results.append(error_log)
        
        successful_count = sum(1 for log in results if log.status == "sent")
        
        self.logger.info(
            "Bulk email send completed",
            total_recipients=len(recipients),
            successful_emails=successful_count,
            failed_emails=len(recipients) - successful_count,
        )
        
        return results
    
    def test_connection(self) -> bool:
        """
        Test SMTP connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            smtp_client = self._connect()
            self._disconnect(smtp_client)
            return True
        except Exception as e:
            self.logger.error("SMTP connection test failed", error=str(e))
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Cleanup if needed
        pass
