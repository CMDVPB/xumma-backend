import email
import json
import logging
# from celery import shared_task
from ayy.models import UserEmail
from xumma.celery import app
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone
from smtplib import SMTPException

logger = logging.getLogger(__name__)


@app.task(bind=True, autoretry_for=(SMTPException,), retry_backoff=30, retry_kwargs={'max_retries': 3})
def send_basic_email_task(self, email_id):
    """
    payload = {
        'to': [...],
        'cc': [...],
        'subject': '',
        'body': '',
        'reply_to': ''
    }
    """

    try:
        with get_connection(
            host=settings.EMAIL_HOST_AWS,
            port=settings.EMAIL_PORT_AWS,
            username=settings.EMAIL_HOST_USER_AWS,
            password=settings.EMAIL_HOST_PASSWORD_AWS,
            use_tls=settings.EMAIL_USE_TLS_AWS
        ) as connection:

            email = UserEmail.objects.get(id=email_id)

            msg = EmailMessage(
                subject=email.subject,
                body=email.body,
                from_email=email.from_email,
                to=email.to,
                cc=email.cc or [],
                reply_to=[email.user.email],
                connection=connection
            )

            msg.content_subtype = "html"
            msg.send()

        email.status = "sent"
        email.sent_at = timezone.now()
        email.save(update_fields=["status", "sent_at"])

        logger.info(f"Email sent to {email.to}")

    except SMTPException as e:
        email.status = "failed"
        email.error = str(e)
        email.save(update_fields=["status", "error"])

        logger.error(f"Email sending failed: {e}")
        raise
