from django.db import transaction
from django.core.exceptions import ValidationError

from att.models import Contact, ContactStatus, ContactStatusHistory


def change_contact_status(
    *,
    contact: Contact,
    new_status: ContactStatus,
    user=None,
    reason: str | None = None
):
    if contact.status == new_status:
        return

    with transaction.atomic():
        old_status = contact.status
        contact.status = new_status
        contact.save(update_fields=["status", "status_updated_at"])

        ContactStatusHistory.objects.create(
            contact=contact,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by=user
        )


def update_contact_status_service(
    *,
    contact,
    status,
    user,
    reason=None
):
    if contact.status == status:
        raise ValidationError("Contact already has this status")

    # example permission rule
    if status.is_blocking and not user.is_staff:
        raise ValidationError("You are not allowed to block a contact")

    change_contact_status(
        contact=contact,
        new_status=status,
        user=user,
        reason=reason
    )
