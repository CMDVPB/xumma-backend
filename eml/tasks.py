import email
import json
import logging
from axx.models import Load, LoadEvent
from ayy.models import UserEmail
from xumma.celery import app
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone
from django.db import IntegrityError
from smtplib import SMTPException

logger = logging.getLogger(__name__)


@app.task(bind=True, autoretry_for=(SMTPException,), retry_backoff=30, retry_kwargs={'max_retries': 3})
def send_basic_email_task(self, email_id, load_uf=None, event_type=None):
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
        email = UserEmail.objects.select_related(
            "user").prefetch_related("email_attachments").get(id=email_id)

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

            # ✅ Attach files (optional)
            for attachment in email.email_attachments.all():
                msg.attach_file(attachment.file.path)

            msg.send()

        now = timezone.now()

        email.status = "sent"
        email.sent_at = now
        email.save(update_fields=["status", "sent_at"])

        ### Prevent duplicate updates on retry ###
        if load_uf and event_type:
            try:
                LoadEvent.objects.create(
                    load_id=Load.objects.only("id").get(uf=load_uf).id,
                    event_type=event_type,
                    created_by=email.user,
                )
            except IntegrityError:
                pass

        logger.info(f"Email sent to {email.to}")

    except SMTPException as e:
        email.status = "failed"
        email.error = str(e)
        email.save(update_fields=["status", "error"])

        logger.error(f"Email sending failed: {e}")
        raise
