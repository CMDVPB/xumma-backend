
from django.dispatch import receiver
from django.db.models.signals import post_save


from axx.models import Trip
from azz.tasks import match_unmatched_import_rows


@receiver(post_save, sender=Trip)
def on_trip_closed(sender, instance, **kwargs):
    if instance.date_end:
        match_unmatched_import_rows.delay(company_id=instance.company_id)
