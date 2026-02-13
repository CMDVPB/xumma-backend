from django.contrib.auth import get_user_model
from datetime import date
from datetime import datetime, timedelta
from abb.utils import get_user_company
from att.models import VehicleDocument
from ayy.models import UserDocument
from bbo.models import Notification

INFO_DAYS = 30
WARNING_DAYS = 7


def calculate_severity(expiration_value):

    if not expiration_value:
        return None

    # Normalize datetime → date
    if isinstance(expiration_value, datetime):
        expiration_value = expiration_value.date()

    today = date.today()
    delta = (expiration_value - today).days

    if delta < 0:
        return Notification.Severity.CRITICAL

    if delta <= WARNING_DAYS:
        return Notification.Severity.WARNING

    if delta <= INFO_DAYS:
        return Notification.Severity.INFO

    return None


def is_birthday_today(date_of_birth):
    if not date_of_birth:
        return False

    today = date.today()

    return (
        date_of_birth.month == today.month
        and date_of_birth.day == today.day
    )


User = get_user_model()


def upsert_expiration_notification(*, company, type, obj_type, obj_id, severity, due_date, payload):
    Notification.objects.update_or_create(
        company=company,
        type=type,
        related_object_type=obj_type,
        related_object_id=obj_id,
        due_date=due_date,
        defaults={
            "severity": severity,
            "payload": payload,
        }
    )


def get_next_birthday(date_of_birth):
    today = date.today()

    try:
        birthday_this_year = date(
            year=today.year,
            month=date_of_birth.month,
            day=date_of_birth.day,
        )
    except ValueError:
        # Handles Feb 29 → fallback to Feb 28
        birthday_this_year = date(today.year, 2, 28)

    if birthday_this_year < today:
        try:
            return birthday_this_year.replace(year=today.year + 1)
        except ValueError:
            return date(today.year + 1, 2, 28)

    return birthday_this_year


def is_birthday_tomorrow(date_of_birth):
    if not date_of_birth:
        return False

    tomorrow = date.today() + timedelta(days=1)
    next_birthday = get_next_birthday(date_of_birth)

    return next_birthday == tomorrow


def process_user_birthdays():

    today = date.today()

    users = User.objects.exclude(date_of_birth__isnull=True)

    for user in users:

        user_company = get_user_company(user)

        if not is_birthday_tomorrow(user.date_of_birth):
            continue

        upsert_expiration_notification(
            company=user_company,
            type=Notification.Type.BIRTHDAY,
            obj_type="user",
            obj_id=user.id,
            due_date=today,
            severity=Notification.Severity.INFO,

            payload={
                "event": "birthday",
                "entity_type": "driver",
                "entity_name": str(user),
                "user_uf": user.uf,
            }
        )


def process_driver_documents():
    today = date.today()

    docs = UserDocument.objects.exclude(date_expiry__isnull=True)

    for doc in docs:
        severity = calculate_severity(doc.date_expiry)

        if not severity:
            continue

        user_company = get_user_company(doc.user)

        upsert_expiration_notification(
            company=user_company,
            type=Notification.Type.DOCUMENT_EXPIRY,
            obj_type="driver",
            obj_id=doc.user_id,
            due_date=doc.date_expiry,
            severity=severity,

            payload={
                "document_type": doc.document_type.name,
                "entity_type": "driver",
                "entity_name": str(doc.user),
                "expiry_date": doc.date_expiry.isoformat(),
                "user_uf": doc.user.uf,
            }

        )


def process_vehicle_documents():
    today = date.today()

    docs = VehicleDocument.objects.exclude(date_expiry__isnull=True)

    for doc in docs:
        severity = calculate_severity(doc.date_expiry)

        if not severity:
            continue

        user_company = doc.vehicle.company

        upsert_expiration_notification(
            company=user_company,
            type=Notification.Type.DOCUMENT_EXPIRY,
            obj_type="vehicle",
            obj_id=doc.vehicle_id,
            due_date=doc.date_expiry,
            severity=severity,

            payload={
                "document_type": doc.document_type.name,
                "entity_type": "vehicle",
                "entity_name": str(doc.vehicle),
                "expiry_date": doc.date_expiry.isoformat(),
                "vehicle_uf": doc.vehicle.uf,
            }
        )


def cleanup_resolved_notifications():
    today = date.today()

    Notification.objects.filter(
        type=Notification.Type.DOCUMENT_EXPIRY,
        due_date__gt=today + timedelta(days=INFO_DAYS)
    ).delete()
