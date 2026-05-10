import logging
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import settings

logger = logging.getLogger(__name__)


class EmailDelivery:
    """Handles email delivery using AWS SES"""
    
    def __init__(self):
        try:
            # Initialize SES client
            self.ses_client = boto3.client(
                'ses',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            
            # Test connection by getting send quota
            self.ses_client.get_send_quota()
            logger.info("AWS SES connection established")
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to connect to AWS SES: {e}")
            self.ses_client = None
    
    def send_report(self, html_body, pdf_path=None, subject=None):
        """Send the competitive intelligence report via email"""
        if not self.ses_client:
            logger.error("SES client not available, cannot send email")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            
            # Set subject
            if subject:
                msg_subject = subject
            else:
                msg_subject = f"{settings.report_title} - {datetime.now().strftime('%B %d, %Y')}"
            
            msg['Subject'] = msg_subject
            msg['From'] = settings.email_from
            
            # Add recipients
            if isinstance(settings.email_to, list):
                msg['To'] = ', '.join(settings.email_to)
                destinations = settings.email_to
            else:
                msg['To'] = settings.email_to
                destinations = [settings.email_to]
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Attach PDF if available
            if pdf_path and os.path.exists(pdf_path):
                try:
                    with open(pdf_path, "rb") as f:
                        pdf_part = MIMEApplication(f.read(), name=os.path.basename(pdf_path))
                        pdf_part.add_header(
                            'Content-Disposition',
                            'attachment',
                            filename=os.path.basename(pdf_path)
                        )
                        msg.attach(pdf_part)
                    logger.info(f"PDF attachment added: {pdf_path}")
                except Exception as e:
                    logger.error(f"Error attaching PDF: {e}")
            else:
                logger.warning("No PDF attachment available")
            
            # Send email
            response = self.ses_client.send_raw_email(
                Source=settings.email_from,
                Destinations=destinations,
                RawMessage={'Data': msg.as_bytes()}
            )
            
            logger.info(f"Email sent successfully! Message ID: {response.get('MessageId')}")
            return True
            
        except ClientError as e:
            logger.error(f"Error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
    
    def test_connection(self):
        """Test AWS SES connection and configuration"""
        if not self.ses_client:
            return {"status": "error", "message": "SES client not initialized"}
        
        try:
            # Get send quota
            quota = self.ses_client.get_send_quota()
            
            # Get verified identities
            identities = self.ses_client.list_identities()
            
            return {
                "status": "success",
                "quota": {
                    "max_24_hour_send": quota['Max24HourSend'],
                    "max_send_rate": quota['MaxSendRate'],
                    "sent_last_24_hours": quota['SentLast24Hours']
                },
                "verified_identities": identities['Identities']
            }
            
        except ClientError as e:
            return {"status": "error", "message": str(e)}
    
    def send_test_email(self):
        """Send a test email to verify configuration"""
        if not self.ses_client:
            return False
        
        try:
            test_html = """
            <html>
            <body>
                <h2>Test Email from Competitive Intelligence System</h2>
                <p>This is a test email to verify that the email delivery system is working correctly.</p>
                <p>Generated at: {}</p>
            </body>
            </html>
            """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            return self.send_report(
                html_body=test_html,
                subject="Test Email - Competitive Intelligence System"
            )
            
        except Exception as e:
            logger.error(f"Error sending test email: {e}")
            return False


# Backward compatibility function
def send_email(html_body, pdf_path):
    """Legacy function for backward compatibility"""
    delivery = EmailDelivery()
    return delivery.send_report(html_body, pdf_path)


def send_email_with_subject(html_body, pdf_path, subject):
    """Enhanced function with custom subject"""
    delivery = EmailDelivery()
    return delivery.send_report(html_body, pdf_path, subject)