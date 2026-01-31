from cld.models import ActivityLog


def log_activity(
    *,
    company,
    user,
    action,
    entity_type,
    entity_id,
    metadata=None,
):
    ActivityLog.objects.create(
        company=company,
        created_by=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )
