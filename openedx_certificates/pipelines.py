"""TODO: Add some docstring here. We may also want to move this to a different file."""

from django.contrib.auth.models import User
from edx_ace import Message, Recipient, ace


def send_email(user: User, certificate_link: str):
    """Send a certificate link to the student."""
    msg = Message(
        name="Certificate",
        app_label="openedx_certificates",
        recipient=Recipient(lms_user_id=user.id, email_address=user.email),
        language='en',
        context={
            'certificate_link': certificate_link,
        },
    )
    ace.send(msg)
