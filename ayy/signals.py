from django.dispatch import receiver
from django.db.models.signals import post_delete

from ayy.models import FileUpload


import logging
logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FileUpload)
def delete_file_upload_on_S3(sender, instance, **kwargs):
    try:
        instance.file_obj.delete(False)
    except Exception as e:
        print('ES173', e)
        logger.error(f'ERRORLOG173 delete_file_upload_on_S3. Error: {e}')
        pass
