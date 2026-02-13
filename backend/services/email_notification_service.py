"""
Email Notification Service
Send email notifications for sync completions and important events.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, List

# Email configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@2ndbrain.ai')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', '2nd Brain')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3006')


class EmailNotificationService:
    """
    Service for sending email notifications.

    Features:
    - Sync completion notifications
    - Error alerts
    - HTML email templates
    - SMTP with TLS

    Configuration (environment variables):
        SMTP_HOST: SMTP server hostname (default: smtp.gmail.com)
        SMTP_PORT: SMTP server port (default: 587)
        SMTP_USER: SMTP username/email
        SMTP_PASSWORD: SMTP password or app password
        SMTP_FROM_EMAIL: From email address
        SMTP_FROM_NAME: From name

    Example (Gmail):
        SMTP_HOST=smtp.gmail.com
        SMTP_PORT=587
        SMTP_USER=your-email@gmail.com
        SMTP_PASSWORD=your-app-password  # Generate at https://myaccount.google.com/apppasswords
        SMTP_FROM_EMAIL=noreply@yourdomain.com
        SMTP_FROM_NAME="2nd Brain"
    """

    def __init__(self):
        self.enabled = bool(SMTP_USER and SMTP_PASSWORD)

        if not self.enabled:
            print("[EmailService] Email notifications disabled (SMTP not configured)")
        else:
            print(f"[EmailService] Email notifications enabled (SMTP: {SMTP_HOST}:{SMTP_PORT})")

    def send_sync_complete_notification(
        self,
        user_email: str,
        connector_type: str,
        total_items: int,
        processed_items: int,
        failed_items: int,
        duration_seconds: float,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Send notification when sync completes.

        Args:
            user_email: Email address of user
            connector_type: Type of connector (gmail, slack, box, github)
            total_items: Total items found
            processed_items: Successfully processed items
            failed_items: Failed items
            duration_seconds: Sync duration
            error_message: Error message if sync failed

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            print("[EmailService] Skipping notification (not configured)")
            return False

        # Format duration
        if duration_seconds < 60:
            duration_str = f"{duration_seconds:.1f} seconds"
        else:
            minutes = int(duration_seconds / 60)
            seconds = int(duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"

        # Determine status
        if error_message:
            status = "Failed"
            status_color = "#DC2626"  # Red
        elif failed_items > 0:
            status = "Completed with errors"
            status_color = "#F59E0B"  # Orange
        else:
            status = "Completed successfully"
            status_color = "#10B981"  # Green

        # Build HTML email - Clean, minimalistic design
        subject = f"Sync {status}: {connector_type.title()}"

        # Status indicator styles
        if error_message:
            status_bg = "#FEF2F2"
            status_border = "#FECACA"
            status_text = "#991B1B"
            status_icon = "✗"
        elif failed_items > 0:
            status_bg = "#FFFBEB"
            status_border = "#FDE68A"
            status_text = "#92400E"
            status_icon = "⚠"
        else:
            status_bg = "#F0FDF4"
            status_border = "#BBF7D0"
            status_text = "#166534"
            status_icon = "✓"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 520px; margin: 0 auto;">
        <tr>
            <td style="padding: 40px 24px;">

                <!-- Logo/Brand -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td style="padding-bottom: 32px;">
                            <span style="font-size: 18px; font-weight: 600; color: #111827;">2nd Brain</span>
                        </td>
                    </tr>
                </table>

                <!-- Status Badge -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td style="padding-bottom: 24px;">
                            <span style="display: inline-block; padding: 6px 12px; background-color: {status_bg}; border: 1px solid {status_border}; border-radius: 6px; font-size: 13px; font-weight: 500; color: {status_text};">
                                {status_icon} {status}
                            </span>
                        </td>
                    </tr>
                </table>

                <!-- Main Content -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td style="padding-bottom: 24px;">
                            <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #111827; line-height: 1.3;">
                                {connector_type.title()} sync finished
                            </h1>
                            <p style="margin: 0; font-size: 15px; color: #6B7280; line-height: 1.5;">
                                Your knowledge base has been updated.
                            </p>
                        </td>
                    </tr>
                </table>

                <!-- Stats -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #F9FAFB; border-radius: 8px;">
                    <tr>
                        <td style="padding: 20px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                                        <span style="font-size: 13px; color: #6B7280;">Items processed</span>
                                    </td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB; text-align: right;">
                                        <span style="font-size: 13px; font-weight: 600; color: #111827;">{processed_items:,}</span>
                                    </td>
                                </tr>
                                {f'''<tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                                        <span style="font-size: 13px; color: #6B7280;">Failed</span>
                                    </td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB; text-align: right;">
                                        <span style="font-size: 13px; font-weight: 600; color: #DC2626;">{failed_items:,}</span>
                                    </td>
                                </tr>''' if failed_items > 0 else ''}
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="font-size: 13px; color: #6B7280;">Duration</span>
                                    </td>
                                    <td style="padding: 8px 0; text-align: right;">
                                        <span style="font-size: 13px; font-weight: 600; color: #111827;">{duration_str}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                {f'''<!-- Error Message -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 16px;">
                    <tr>
                        <td style="padding: 16px; background-color: #FEF2F2; border-radius: 8px; border-left: 3px solid #DC2626;">
                            <p style="margin: 0; font-size: 13px; color: #991B1B;">{error_message}</p>
                        </td>
                    </tr>
                </table>''' if error_message else ''}

                <!-- CTA Button -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td style="padding-top: 32px;">
                            <a href="{FRONTEND_URL}/documents" style="display: inline-block; padding: 12px 24px; background-color: #111827; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 500; border-radius: 6px;">
                                View documents →
                            </a>
                        </td>
                    </tr>
                </table>

                <!-- Footer -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td style="padding-top: 48px; border-top: 1px solid #E5E7EB; margin-top: 32px;">
                            <p style="margin: 0; font-size: 12px; color: #9CA3AF; line-height: 1.5;">
                                Sent by 2nd Brain · <a href="{FRONTEND_URL}/settings" style="color: #9CA3AF;">Notification settings</a>
                            </p>
                        </td>
                    </tr>
                </table>

            </td>
        </tr>
    </table>
</body>
</html>
"""

        text_body = f"""
2nd Brain Sync Complete

Your {connector_type.title()} integration sync has finished.

Status: {status}

Stats:
- Total Items Found: {total_items:,}
- Successfully Processed: {processed_items:,}
{f'- Failed: {failed_items:,}' if failed_items > 0 else ''}
- Duration: {duration_str}
- Completed At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

{f'Error: {error_message}' if error_message else ''}

Your knowledge base has been updated with the latest information from {connector_type.title()}.

View your documents: {FRONTEND_URL}/documents
"""

        return self._send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg['To'] = to_email

            # Attach parts
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Connect and send
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()

            print(f"[EmailService] Sent notification to {to_email}: {subject}")
            return True

        except Exception as e:
            print(f"[EmailService] Failed to send email to {to_email}: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
_email_service = None

def get_email_service() -> EmailNotificationService:
    """Get the global EmailNotificationService instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailNotificationService()
    return _email_service
