from cld.models import ActivityLog, CalendarEvent
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime


DATETIME_FIELDS = {"start", "end"}


def is_latest_log(log: ActivityLog) -> bool:
    return not ActivityLog.objects.filter(
        company=log.company,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        created_at__gt=log.created_at,
    ).exists()


def apply_reverse_patch(event, reverse_patch):
    for field, change in reverse_patch.items():
        value = change["to"]
        if field in DATETIME_FIELDS:
            value = parse_datetime(value)
        setattr(event, field, value)


@transaction.atomic
def undo_event_change(*, log: ActivityLog, user):
    if log.reversed_at:
        raise ValueError("Already undone")

    if not log.is_reversible:
        raise ValueError("Not undoable")

    if not is_latest_log(log):
        raise ValueError("Only the latest change can be undone")

    if log.entity_type != "calendar_event":
        raise ValueError("Unsupported entity")

    if log.action == "event_updated":
        event = CalendarEvent.objects.select_for_update().get(id=log.entity_id)
        apply_reverse_patch(event, log.reverse_metadata)
        event.save(update_fields=list(log.reverse_metadata.keys()))

    elif log.action == "event_created":
        CalendarEvent.objects.filter(id=log.entity_id).delete()

    elif log.action == "event_deleted":
        snap = log.reverse_metadata.get("snapshot")
        CalendarEvent.objects.create(
            id=snap["id"],
            calendar_id=snap["calendar_id"],
            title=snap["title"],
            description=snap["description"],
            start=parse_datetime(snap["start"]),
            end=parse_datetime(snap["end"]),
            all_day=snap["all_day"],
            color=snap["color"],
            created_by_id=snap["created_by_id"],
        )

    else:
        raise ValueError("Unsupported action")

    # mark original log
    log.reversed_at = timezone.now()
    log.reversed_by = user
    log.save(update_fields=["reversed_at", "reversed_by"])

    # write undo audit entry
    ActivityLog.objects.create(
        company=log.company,
        user=user,
        action="event_undo",
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        metadata={
            "undone_action": log.action,
            "undone_log_id": str(log.id),
        },
        is_reversible=False,
    )
