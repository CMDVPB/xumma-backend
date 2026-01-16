from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.db.models.signals import post_save

from abb.constants import SYSTEM_LABELS
from ayy.models import MailLabelV2


import logging
logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def create_mail_labels(sender, instance, created, **kwargs):
    if not created:
        return

    for slug, name, order in SYSTEM_LABELS:
        MailLabelV2.objects.create(
            user=instance,
            slug=slug,
            name=name,
            type=MailLabelV2.SYSTEM,
            order=order,
        )
