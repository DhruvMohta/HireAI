import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# SMTP server configuration
# SMTP server configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "mail.gifuzzz.eu")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "holyhack2025@gifuzzz.eu")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "holyhack2025@gifuzzz.eu")

def sendMail(to, subject, body):
    """
    Send an email using the configured SMTP server
    
    Args:
        to (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Create email message
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Establish connection and send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to, msg.as_string())
        
        print("Email sent successfully.")
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Example usage when script is run directly
if __name__ == "__main__":
    RECIPIENT_EMAIL = "demo@gifuzzz.eu"
    test_subject = "Test Email from Custom Mailserver"
    test_body = """
    Dear,

    Your job application has been approved! Congratulations!
    """
    
    sendMail(RECIPIENT_EMAIL, test_subject, test_body)
