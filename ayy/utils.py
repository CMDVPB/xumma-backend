import uuid
import os


def user_photo_upload_path(instance, filename):
    """
    Upload path for user photos on the local server:
    media/user_photos/<user_id>/<uuid>.<ext>
    """
    ext = filename.split('.')[-1]  # get file extension
    filename = f"{uuid.uuid4()}.{ext}"  # rename to UUID to avoid collisions
    return os.path.join('user_photos', str(instance.user.id), filename)


def dynamic_upload_path(instance, filename):
    # Determine the folder based on the related foreign key
    if instance.inv:
        folder = 'inv_files'
    else:
        folder = 'expspv_files'

    # Build the upload path
    return os.path.join(folder, filename)


def build_card_periods(card):
    from ayy.models import CardAssignment
    events = card.card_assignments.order_by("assigned_at")

    periods = []
    current = None

    for e in events:

        if e.action == CardAssignment.ASSIGN:
            current = {
                "start": e.assigned_at,
                "employee": e.employee,
                "vehicle": e.vehicle,
            }

        elif e.action == CardAssignment.UNASSIGN and current:
            periods.append({
                **current,
                "end": e.assigned_at
            })
            current = None

    # Still assigned → open period
    if current:
        periods.append({
            **current,
            "end": None
        })

    return periods


def build_employee_periods(employee):
    from ayy.models import CardAssignment

    events = CardAssignment.objects.filter(
        employee=employee
    ).order_by("assigned_at")

    periods = []
    current = None

    for e in events:

        if e.action == CardAssignment.ASSIGN:
            current = {"card": e.card, "start": e.assigned_at}

        elif e.action == CardAssignment.UNASSIGN and current:
            periods.append({
                **current,
                "end": e.assigned_at
            })
            current = None

    if current:
        periods.append({**current, "end": None})

    return periods


def build_periods(card):
    from ayy.models import CardAssignment
    events = card.card_assignments.order_by("assigned_at")

    periods = []
    active = None

    for e in events:

        if e.action == CardAssignment.ASSIGN:
            active = {
                "start": e.assigned_at,
                "end": None,
                "employee": e.employee,
                "vehicle": e.vehicle,
                "assigned_by": e.assigned_by,
            }

        elif e.action == CardAssignment.UNASSIGN and active:
            active["end"] = e.assigned_at
            periods.append(active)
            active = None

    if active:
        periods.append(active)

    return periods
