from collections import OrderedDict

from axx.models import LoadMovement


def sync_load_movements_for_load(load):
    """
    Sync current expected warehouse movements from load.entry_loads.

    Rules:
    - create/update one `expected_warehouse` movement per relevant entry warehouse
    - preserve historical rows with other statuses
    - delete only stale `expected_warehouse` rows that no longer apply
    """

    entry_loads = list(
        load.entry_loads.select_related('warehouse').all()
    )

    expected_targets = []
    for entry in entry_loads:
        if not entry.warehouse_id:
            continue

        role = None
        if entry.action == 'loading':
            role = 'loading'
        elif entry.action == 'unloading':
            role = 'unloading'

        expected_targets.append(
            {
                'warehouse_id': entry.warehouse_id,
                'role': role,
                'from_location': entry.action,
                'to_location': 'warehouse',
            }
        )

    # dedupe by warehouse + role
    deduped_targets = list(
        OrderedDict(
            (
                (f"{item['warehouse_id']}::{item['role']}", item)
                for item in expected_targets
            )
        ).values()
    )

    current_expected_qs = load.load_movements.filter(status='expected_warehouse')

    current_expected = list(current_expected_qs)

    target_keys = {
        (item['warehouse_id'], item['role'])
        for item in deduped_targets
    }

    current_keys = {
        (movement.warehouse_id, getattr(movement, 'role', None))
        for movement in current_expected
    }

    # create missing
    for item in deduped_targets:
        key = (item['warehouse_id'], item['role'])
        if key not in current_keys:
            LoadMovement.objects.create(
                load=load,
                trip=load.trip,
                warehouse_id=item['warehouse_id'],
                status='expected_warehouse',
                role=item['role'],
                from_location=item['from_location'],
                to_location=item['to_location'],
            )

    # update existing trip/from/to if still relevant
    for movement in current_expected:
        key = (movement.warehouse_id, getattr(movement, 'role', None))
        if key in target_keys:
            target = next(
                x for x in deduped_targets
                if x['warehouse_id'] == movement.warehouse_id
                and x['role'] == getattr(movement, 'role', None)
            )

            changed = False

            if movement.trip_id != load.trip_id:
                movement.trip = load.trip
                changed = True

            if movement.from_location != target['from_location']:
                movement.from_location = target['from_location']
                changed = True

            if movement.to_location != target['to_location']:
                movement.to_location = target['to_location']
                changed = True

            if changed:
                movement.save(update_fields=['trip', 'from_location', 'to_location'])

    # delete stale expected rows only
    for movement in current_expected:
        key = (movement.warehouse_id, getattr(movement, 'role', None))
        if key not in target_keys:
            movement.delete()