import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def send_email(html_body, pdf_path):
    client = boto3.client('ses', region_name='us-east-1')
    msg = MIMEMultipart()
    msg['Subject'] = "Weekly Competitive Intelligence Report"
    
    # Inline HTML
    msg.attach(MIMEText(html_body, 'html'))
    
    # PDF Attachment
    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read())
        part.add_header('Content-Disposition', 'attachment', filename="Report.pdf")
        msg.attach(part)
        
    client.send_raw_email(Source="ops@yourstartup.com", Destinations=["growth@yourstartup.com"], RawMessage={'Data': msg.as_string()})