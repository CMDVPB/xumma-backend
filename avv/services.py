from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from abb.utils import get_user_company

from .models import (
    Location, Part, PartRequest, PartRequestLine, Reservation,
    StockBalance, StockLot, StockMovement, IssueDocument, IssueLine
)


class InventoryError(Exception):
    pass


@dataclass(frozen=True)
class ReservePolicy:
    """
    FIFO by default. Extend for FEFO, cheapest, etc.
    """
    fifo: bool = True
    allow_partial: bool = True


def _select_candidate_balances_for_part(part_id: int, warehouse_id: Optional[int] = None):
    qs = (
        StockBalance.objects
        .select_related("lot", "location", "location__warehouse")
        .filter(part_id=part_id)
        .filter(qty_on_hand__gt=0)
    )
    if warehouse_id:
        qs = qs.filter(location__warehouse_id=warehouse_id)

    # FIFO: earlier received lots first
    return qs.order_by("lot__received_at", "lot_id", "location_id")


@transaction.atomic
def reserve_request(
    *,
    request_id: int,
    actor_user,
    warehouse_id: Optional[int] = None,
    policy: ReservePolicy = ReservePolicy(),
) -> PartRequest:
    """
    Reserves stock for each line by locking StockBalance rows.
    Creates Reservation rows and increments qty_reserved in balances.
    """
    req = PartRequest.objects.select_for_update().get(id=request_id)
    user_company = get_user_company(actor_user)

    if req.status not in [PartRequest.Status.SUBMITTED, PartRequest.Status.APPROVED]:
        raise InventoryError(
            f"Request {req.id} must be SUBMITTED/APPROVED to reserve. Current: {req.status}")

    # clear existing reservations (safe re-reserve flow)
    Reservation.objects.filter(line__request=req).delete()

    lines = list(
        PartRequestLine.objects.select_for_update()
        .filter(request=req)
        .select_related("part")
    )

    any_partial = False

    for line in lines:
        needed = line.qty_requested - line.qty_issued  # if some already issued
        if needed <= 0:
            line.qty_reserved = Decimal("0")
            line.save(update_fields=["qty_reserved"])
            continue

        # Lock candidate balances so two storekeepers can't reserve same items.
        candidates = (
            _select_candidate_balances_for_part(
                line.part_id, warehouse_id=warehouse_id)
            .select_for_update()
        )

        reserved_total = Decimal("0")
        for bal in candidates:
            if reserved_total >= needed:
                break
            available = bal.qty_on_hand - bal.qty_reserved
            if available <= 0:
                continue

            take = min(available, needed - reserved_total)
            if take <= 0:
                continue

            # Update balance reserved qty
            StockBalance.objects.filter(id=bal.id).update(
                qty_reserved=F("qty_reserved") + take)

            Reservation.objects.create(
                company=user_company,
                line=line,
                balance=bal,
                qty=take,
                created_by=actor_user,
                created_at=timezone.now(),
            )
            reserved_total += take

        if reserved_total < needed:
            if not policy.allow_partial:
                raise InventoryError(
                    f"Not enough stock to reserve part {line.part.sku}. Needed {needed}, reserved {reserved_total}."
                )
            any_partial = True

        line.qty_reserved = reserved_total
        line.save(update_fields=["qty_reserved"])

    req.status = PartRequest.Status.PARTIAL if any_partial else PartRequest.Status.RESERVED
    req.save(update_fields=["status"])
    return req


@transaction.atomic
@transaction.atomic
def issue_request(*, request_id: int, actor_user) -> IssueDocument:
    req = PartRequest.objects.select_for_update().get(id=request_id)
    user_company = get_user_company(actor_user)

    if req.status not in [PartRequest.Status.RESERVED, PartRequest.Status.PARTIAL]:
        raise InventoryError(
            f"Request {req.id} must be RESERVED/PARTIAL to issue. Current: {req.status}"
        )

    doc = IssueDocument.objects.create(
        company=user_company,
        request=req,
        mechanic=req.mechanic,
        vehicle=req.vehicle,
        driver=req.driver,
        created_by=actor_user,
    )

    lines = {
        ln.id: ln
        for ln in PartRequestLine.objects.select_for_update()
        .filter(request=req)
    }

    reservations = (
        Reservation.objects
        .select_for_update()
        .select_related(
            "balance",
            "balance__lot",
            "balance__location",
            "line",
        )
        .filter(line__request=req)
        .order_by("balance__lot__received_at", "id")
    )

    for r in reservations:
        bal = r.balance
        qty = r.qty

        if qty <= 0:
            continue

        if bal.qty_reserved < qty:
            raise InventoryError(
                f"Reserved mismatch on balance {bal.id}: "
                f"reserved={bal.qty_reserved}, need={qty}"
            )

        if bal.qty_on_hand < qty:
            raise InventoryError(
                f"Stock mismatch on balance {bal.id}: "
                f"on_hand={bal.qty_on_hand}, need={qty}"
            )

        # update balance atomically
        StockBalance.objects.filter(id=bal.id).update(
            qty_reserved=F("qty_reserved") - qty,
            qty_on_hand=F("qty_on_hand") - qty,
        )

        IssueLine.objects.create(
            company=user_company,
            doc=doc,
            part=bal.part,
            lot=bal.lot,
            from_location=bal.location,
            qty=qty,
            created_by=actor_user,
        )

        StockMovement.objects.create(
            company=user_company,
            type=StockMovement.Type.ISSUE,
            part=bal.part,
            lot=bal.lot,
            from_location=bal.location,
            qty=qty,
            unit_cost_snapshot=bal.lot.unit_cost,
            currency=bal.lot.currency,
            ref_type="IssueDocument",
            ref_id=str(doc.id),
            created_by=actor_user,
        )

        line = lines[r.line_id]
        line.qty_issued += qty
        line.qty_reserved = max(Decimal("0"), line.qty_reserved - qty)
        line.save(update_fields=["qty_issued", "qty_reserved"])

    Reservation.objects.filter(line__request=req).delete()

    remaining = (
        PartRequestLine.objects
        .filter(request=req)
        .annotate(rem=F("qty_requested") - F("qty_issued"))
        .filter(rem__gt=0)
        .exists()
    )

    req.status = (
        PartRequest.Status.PARTIAL if remaining else PartRequest.Status.ISSUED
    )
    req.save(update_fields=["status"])

    return doc


class InventoryError(Exception):
    pass


@transaction.atomic
def receive_stock(*, data, user):
    if data["qty"] <= 0:
        raise InventoryError("Quantity must be greater than zero")

    company = get_user_company(user)

    part = Part.objects.select_for_update().get(
        id=data["part"].id,
        company=company,
        is_active=True,
    )

    location = Location.objects.select_related("warehouse").get(
        id=data["location"].id,
        company=company,
    )

    # 1️⃣ Create lot
    lot = StockLot.objects.create(
        company=company,
        part=part,
        supplier_name=data.get("supplier_name", ""),
        unit_cost=data.get("unit_cost", Decimal("0")),
        received_at=timezone.now(),
        expiry_date=data.get("expiry_date"),
        created_by=user,
    )

    # 2️⃣ Ledger movement
    StockMovement.objects.create(
        company=company,
        type=StockMovement.Type.RECEIPT,
        part=part,
        lot=lot,
        to_location=location,
        qty=data["qty"],
        unit_cost_snapshot=lot.unit_cost,
        currency=lot.currency,
        ref_type="RECEIPT",
        ref_id=str(lot.id),
        created_by=user,
    )

    # 3️⃣ Balance (upsert)
    balance, _ = StockBalance.objects.select_for_update().get_or_create(
        company=company,
        part=part,
        location=location,
        lot=lot,
        defaults={
            "qty_on_hand": Decimal("0"),
            "qty_reserved": Decimal("0"),
            "created_by": user,
        },
    )

    balance.qty_on_hand += data["qty"]
    balance.save(update_fields=["qty_on_hand"])

    return balance


def transfer_stock(
    *,
    balance_id: int,
    to_location_id: int,
    qty: Decimal,
    company,
    user,
):
    if qty <= 0:
        raise ValidationError("Quantity must be greater than zero")

    with transaction.atomic():
        # lock source balance
        balance = (
            StockBalance.objects
            .select_for_update()
            .select_related("part", "lot", "location")
            .get(id=balance_id, company=company)
        )

        if balance.qty_available < qty:
            raise ValidationError("Insufficient available stock")

        to_location = Location.objects.get(
            id=to_location_id,
            company=company,
        )

        # create / lock destination balance (same lot)
        dest_balance, _ = StockBalance.objects.select_for_update().get_or_create(
            company=company,
            part=balance.part,
            lot=balance.lot,
            location=to_location,
            defaults={
                "qty_on_hand": Decimal("0"),
                "qty_reserved": Decimal("0"),
                "created_by": user,
            },
        )

        # apply movement
        balance.qty_on_hand -= qty
        balance.save(update_fields=["qty_on_hand"])

        dest_balance.qty_on_hand += qty
        dest_balance.save(update_fields=["qty_on_hand"])

        StockMovement.objects.create(
            company=company,
            created_by=user,
            type=StockMovement.Type.TRANSFER,
            part=balance.part,
            lot=balance.lot,
            from_location=balance.location,
            to_location=to_location,
            qty=qty,
            unit_cost_snapshot=balance.lot.unit_cost,
            ref_type="TRANSFER",
            ref_id=str(balance.id),
        )

        return {
            "from_balance": balance.id,
            "to_balance": dest_balance.id,
            "qty": qty,
        }


@transaction.atomic
def confirm_issue_document(*, doc_id: int, actor_user):
    doc = IssueDocument.objects.select_for_update().get(id=doc_id)

    if doc.mechanic_id != actor_user.id:
        raise PermissionDenied("Only assigned mechanic can confirm")

    if doc.status == IssueDocument.Status.CONFIRMED:
        return doc

    doc.status = IssueDocument.Status.CONFIRMED
    doc.save(update_fields=["status"])

    return doc
