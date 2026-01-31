from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from djoser.signals import user_registered


from .models import Calendar, CalendarMember

User = get_user_model()


@receiver(user_registered)
def create_default_calendar(user, request, **kwargs):

    # Create default calendar
    calendar = Calendar.objects.create(
        name="My Calendar",
        created_by=user,
        is_default=True,
    )

    # Link user as owner
    CalendarMember.objects.create(
        calendar=calendar,
        user=user,
        role="owner",
    )
