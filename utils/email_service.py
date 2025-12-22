import resend
import os
from typing import Optional
from utils.app_logger import createLogger

logger = createLogger("email_service")

# Configure Resend
resend.api_key = os.getenv("RESEND_API_KEY")


class EmailService:

    @staticmethod
    def send_invitation_email(
            to_email: str,
            user_name: str,
            organization_name: str,
            temp_password: str,
            role: str
    ) -> tuple[bool, Optional[str]]:
        """Send invitation email with temporary password"""
        try:
            from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
            app_name = os.getenv("APP_NAME", "Squadra")
            app_url = os.getenv("APP_URL", "http://localhost:8000")

            html_content = f""""""

            # Plain text fallback
            text_content = f"""
Welcome to {organization_name}!

Hi {user_name},

You've been invited to join {organization_name} on {app_name} as a {role.replace('_', ' ').title()}.

Your Login Credentials:
Email: {to_email}
Temporary Password: {temp_password}

Login here: {app_url}/login

Security Notice:
This is a temporary password. Please change it after your first login using the "Forgot Password" feature.

Welcome aboard!
The {app_name} Team

---
© 2024 {app_name}. All rights reserved.
Made in India with ❤️
            """

            params = {
                "from": from_email,
                "to": [to_email],
                "subject": f"Welcome to {organization_name} on {app_name}! 🎉",
                "html": html_content,
                "text": text_content
            }

            response = resend.Emails.send(params)

            logger.info(f"Invitation email sent to {to_email} - Email ID: {response.get('id')}")
            return True, None

        except Exception as e:
            logger.exception(f"Error sending invitation email: {e}")
            return False, str(e)

    @staticmethod
    def send_password_reset_email(
            to_email: str,
            user_name: str,
            reset_link: str
    ) -> tuple[bool, Optional[str]]:
        """Send password reset email (for future use)"""
        try:
            from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
            app_name = os.getenv("APP_NAME", "WayFind")

            # TODO: Create password reset email template
            # Similar structure to invitation email

            logger.info(f"Password reset email sent to {to_email}")
            return True, None

        except Exception as e:
            logger.exception(f"Error sending password reset email: {e}")
            return False, str(e)