from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save

from abb.constants import SYSTEM_LABELS
from ayy.models import FileUpload, MailLabelV2


import logging
logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_delete, sender=FileUpload)
def delete_file_upload_on_S3(sender, instance, **kwargs):
    try:
        instance.file_obj.delete(False)
    except Exception as e:
        print('ES173', e)
        logger.error(f'ERRORLOG173 delete_file_upload_on_S3. Error: {e}')
        pass


@receiver(post_save, sender=User)
def create_mail_labels(sender, instance, created, **kwargs):
    if not created:
        return

    for label_id, name, order in SYSTEM_LABELS:
        MailLabelV2.objects.create(
            id=label_id,
            user=instance,
            name=name,
            type=MailLabelV2.SYSTEM,
            order=order,
        )
