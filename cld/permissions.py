from rest_framework.exceptions import PermissionDenied
from .models import CalendarMember


def require_calendar_write(user, calendar):
    print('3580', calendar)
    if not CalendarMember.objects.filter(
        calendar=calendar,
        user=user,
        role__in=["owner", "editor"],
    ).exists():
        raise PermissionDenied("No write access")


def require_calendar_read(user, calendar):
    if not CalendarMember.objects.filter(
        calendar=calendar,
        user=user,
    ).exists():
        raise PermissionDenied("No access")
