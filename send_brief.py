import os
import sys
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject, body, recipient_email):
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    
    if not smtp_user or not smtp_pass:
        error_msg = "SMTP_USER or SMTP_PASS environment variables are not set."
        print(error_msg, file=sys.stderr)
        with open("error_log.txt", "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {error_msg}\n")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    max_retries = 3
    retry_interval = 15 * 60  # 15 minutes
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt} of {max_retries}: Connecting to smtp.gmail.com:587...")
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.ehlo()
            server.starttls()
            server.ehlo()
            print("Logging in...")
            server.login(smtp_user, smtp_pass)
            print("Sending email...")
            server.sendmail(smtp_user, recipient_email, msg.as_string())
            server.quit()
            print("Email sent successfully!")
            return True
        except Exception as e:
            error_log_msg = f"Attempt {attempt} failed: {str(e)}"
            print(error_log_msg, file=sys.stderr)
            with open("error_log.txt", "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_log_msg}\n")
            if attempt < max_retries:
                print(f"Waiting 15 minutes before retrying...")
                time.sleep(retry_interval)
            else:
                print("All delivery attempts failed.")
                return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python send_brief.py <subject> <brief_file_path> <recipient_email>")
        sys.argv[0]
        sys.exit(1)
        
    subject = sys.argv[1]
    file_path = sys.argv[2]
    recipient = sys.argv[3]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            body = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    success = send_email(subject, body, recipient)
    if not success:
        sys.exit(1)
