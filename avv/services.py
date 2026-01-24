from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

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
def issue_request(
    *,
    request_id: int,
    actor_user,
) -> IssueDocument:
    """
    Issues all reserved quantities:
    - decreases qty_reserved and qty_on_hand on the same locked balance rows
    - writes StockMovement ledger rows (ISSUE)
    - creates IssueDocument + IssueLines
    """
    req = PartRequest.objects.select_for_update().get(id=request_id)

    if req.status not in [PartRequest.Status.RESERVED, PartRequest.Status.PARTIAL]:
        raise InventoryError(
            f"Request {req.id} must be RESERVED/PARTIAL to issue. Current: {req.status}")

    doc = IssueDocument.objects.create(
        request=req,
        mechanic=req.mechanic,
        vehicle=req.vehicle,
        driver=req.driver,
        created_by=actor_user,
        created_at=timezone.now(),
    )

    # Lock lines + reservations
    lines = list(
        PartRequestLine.objects.select_for_update()
        .filter(request=req)
        .select_related("part")
    )

    # Fetch reservations in a deterministic order; lock their balances
    reservations = (
        Reservation.objects
        .select_related("balance", "balance__lot", "balance__location", "line", "line__part")
        .filter(line__request=req)
        .select_for_update(of=("self",))
        .order_by("balance__lot__received_at", "id")
    )

    # Lock related balances
    balance_ids = list(reservations.values_list(
        "balance_id", flat=True).distinct())
    balances = {
        b.id: b for b in StockBalance.objects.select_for_update().filter(id__in=balance_ids).select_related("lot", "location")
    }

    # Issue each reservation fully (simple skeleton). Extend to partial issue if needed.
    for r in reservations:
        bal = balances[r.balance_id]
        qty = r.qty

        if qty <= 0:
            continue

        # Validate availability + reserved integrity
        if bal.qty_reserved < qty:
            raise InventoryError(
                f"Reserved mismatch on balance {bal.id}. reserved={bal.qty_reserved}, need={qty}")
        if bal.qty_on_hand < qty:
            raise InventoryError(
                f"Stock mismatch on balance {bal.id}. on_hand={bal.qty_on_hand}, need={qty}")

        # Update balance
        StockBalance.objects.filter(id=bal.id).update(
            qty_reserved=F("qty_reserved") - qty,
            qty_on_hand=F("qty_on_hand") - qty,
        )

        IssueLine.objects.create(
            doc=doc,
            part=bal.part,
            lot=bal.lot,
            from_location=bal.location,
            qty=qty,
            created_by=actor_user,
            created_at=timezone.now(),
        )

        StockMovement.objects.create(
            type=StockMovement.Type.ISSUE,
            part=bal.part,
            lot=bal.lot,
            from_location=bal.location,
            to_location=None,
            qty=qty,
            unit_cost_snapshot=bal.lot.unit_cost,
            currency=bal.lot.currency,
            ref_type="IssueDocument",
            ref_id=str(doc.id),
            created_by=actor_user,
            created_at=timezone.now(),
        )

        # Update request line totals (issued)
        line = next((ln for ln in lines if ln.id == r.line_id), None)
        if line:
            line.qty_issued = line.qty_issued + qty
            # reserved qty on line is a derived summary; keep simple:
            line.qty_reserved = max(Decimal("0"), line.qty_reserved - qty)
            line.save(update_fields=["qty_issued", "qty_reserved"])

    # Clean up reservations after issuing
    Reservation.objects.filter(line__request=req).delete()

    # Update request status
    # If any line still needs qty, keep PARTIAL, else ISSUED
    req.refresh_from_db()
    remaining = (
        PartRequestLine.objects.filter(request=req)
        .annotate(rem=F("qty_requested") - F("qty_issued"))
        .filter(rem__gt=0)
        .exists()
    )
    req.status = PartRequest.Status.PARTIAL if remaining else PartRequest.Status.ISSUED
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
