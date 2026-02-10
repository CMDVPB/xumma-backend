from collections import defaultdict
from django.db import transaction
from rest_framework import permissions, status
import logging
from django.db.models import QuerySet, Q
from requests import get
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, permissions
from rest_framework import status

from abb.utils import get_user_company
from att.models import Contact, Vehicle
from axx.models import Load
from .models import CMRHolder, CMRStockBatch, CMRStockMovement, CardAssignment, CompanyCard, DocumentType
from .serializers import (
    CompanyCardSerializer,
    DocumentTypeSerializer,
    DocumentTypeCreateSerializer
)


logger = logging.getLogger(__name__)
User = get_user_model()


class DocumentTypeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)
        qs = DocumentType.objects.filter(is_active=True)

        # system + company-specific
        qs = qs.filter(
            Q(is_system=True) |
            Q(company=user_company)
        )

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)

        target = self.request.query_params.get('target')
        if target in dict(DocumentType.TARGET_CHOICES):
            qs = qs.filter(target=target)

        return qs.order_by('order', 'name')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DocumentTypeCreateSerializer
        return DocumentTypeSerializer


class DocumentTypeRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DocumentTypeSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)

        return DocumentType.objects.filter(
            Q(is_system=True) | Q(company=user_company),
            is_active=True,
        )


###### END DOCUMENT TYPES ######


###### START CARDS ######
class CompanyCardListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanyCardSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = CompanyCard.objects.filter(company=company)

        assigned_employee = self.request.query_params.get("assigned_employee")
        if assigned_employee:
            qs = qs.filter(current_employee__uf=assigned_employee)

        assigned_vehicle = self.request.query_params.get("assigned_vehicle")
        if assigned_vehicle:
            qs = qs.filter(current_vehicle__uf=assigned_vehicle)

        return qs.order_by("-id")

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(company=user_company)


class CompanyCardRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanyCardSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return CompanyCard.objects.filter(
            company=user_company
        )


class CompanyCardAssignView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, uf):
        print("ASSIGN PAYLOAD:", request.data, uf)  # 👈 ADD THIS

        user_company = get_user_company(self.request.user)
        card = get_object_or_404(
            CompanyCard,
            uf=uf,
            company=user_company,
        )

        employee_id = request.data.get("employee_id")
        vehicle_id = request.data.get("vehicle_id")

        has_employee = employee_id is not None and employee_id != ""
        has_vehicle = vehicle_id is not None and vehicle_id != ""

        if has_employee == has_vehicle:
            return Response(
                {"detail": "Specify exactly one of employee_id or vehicle_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # unassign previous
        if card.current_employee or card.current_vehicle:
            CardAssignment.objects.create(
                card=card,
                employee=card.current_employee,
                vehicle=card.current_vehicle,
                action=CardAssignment.UNASSIGN,
                assigned_by=request.user,
            )

        card.current_employee = None
        card.current_vehicle = None

        if employee_id:
            card.current_employee = User.objects.get(uf=employee_id)
        else:
            card.current_vehicle = Vehicle.objects.get(uf=vehicle_id)

        card.save()

        CardAssignment.objects.create(
            card=card,
            employee=card.current_employee,
            vehicle=card.current_vehicle,
            action=CardAssignment.ASSIGN,
            assigned_by=request.user,
        )

        return Response(
            CompanyCardSerializer(card).data,
            status=status.HTTP_200_OK,
        )


class CompanyCardUnassignView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, uf):
        card = get_object_or_404(
            CompanyCard,
            uf=uf,
            company=request.user.company,
        )

        if not card.current_employee and not card.current_vehicle:
            return Response(status=status.HTTP_204_NO_CONTENT)

        CardAssignment.objects.create(
            card=card,
            employee=card.current_employee,
            vehicle=card.current_vehicle,
            action=CardAssignment.UNASSIGN,
            assigned_by=request.user,
        )

        card.current_employee = None
        card.current_vehicle = None
        card.save()

        return Response(
            CompanyCardSerializer(card).data,
            status=status.HTTP_200_OK,
        )


###### END CARDS ######


###### START CMR TRANSFER ######
class CMRAvailableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        holder_type = request.query_params.get("holder_type")
        vehicle_uf = request.query_params.get("vehicle_id")
        customer_uf = request.query_params.get("customer_id")

        if holder_type not in ("COMPANY", "VEHICLE", "CUSTOMER"):
            return Response(
                {"detail": "Invalid holder_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = get_user_company(request.user)

        # Resolve holder (if not company)
        holder = None
        if holder_type == "VEHICLE":
            if not vehicle_uf:
                return Response(
                    {"detail": "vehicle_uf is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            holder = (
                CMRHolder.objects
                .select_related("vehicle")
                .filter(vehicle__uf=vehicle_uf)
                .first()
            )

        elif holder_type == "CUSTOMER":
            if not customer_uf:
                return Response(
                    {"detail": "customer_uf is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            holder = (
                CMRHolder.objects
                .select_related("customer")
                .filter(customer__uf=customer_uf)
                .first()
            )
        # All batches for company
        batches = CMRStockBatch.objects.filter(company=company)

        result = []

        for batch in batches:
            # All movements for this batch
            movements = (
                batch.movements
                .exclude(movement_type=CMRStockMovement.CONSUMED)
                .order_by("number_from")
            )

            # Start with full batch range
            available_ranges = [
                (batch.number_from, batch.number_to)
            ]

            # Subtract transferred ranges that are NOT owned by this holder
            for m in movements:
                if m.movement_type != CMRStockMovement.TRANSFER:
                    continue

                # Determine current owner of this movement
                if holder_type == "COMPANY":
                    owned = m.to_holder is None
                else:
                    owned = m.to_holder_id == (holder.id if holder else None)

                if owned:
                    continue  # still available for this holder

                # Remove [m.number_from, m.number_to] from available_ranges
                new_ranges = []
                for start, end in available_ranges:
                    if m.number_to < start or m.number_from > end:
                        new_ranges.append((start, end))
                        continue

                    if start < m.number_from:
                        new_ranges.append((start, m.number_from - 1))
                    if m.number_to < end:
                        new_ranges.append((m.number_to + 1, end))

                available_ranges = new_ranges

            # Emit ranges
            for start, end in available_ranges:
                if start > end:
                    continue

                result.append({
                    "batch_id": batch.id,
                    "batch_uf": batch.uf,
                    "series": batch.series,
                    "number_from": start,
                    "number_to": end,
                    "quantity": end - start + 1,
                })

        return Response(result, status=status.HTTP_200_OK)


class CMRTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data

        print("RAW TRANSFER DATA →", data)

        # -----------------------------
        # Validate basic input
        # -----------------------------
        batch_uf = data.get("batch_uf")
        number_from = data.get("number_from")
        number_to = data.get("number_to")

        try:
            number_from = int(number_from)
            number_to = int(number_to)
        except (TypeError, ValueError):
            return Response(
                {"detail": "number_from and number_to must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not all([batch_uf, number_from, number_to]):
            return Response(
                {"detail": "batch_uf, number_from, number_to are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if number_from > number_to:
            return Response(
                {"detail": "number_from must be <= number_to"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------
        # Resolve batch
        # -----------------------------
        company = get_user_company(request.user)

        batch = CMRStockBatch.objects.filter(
            uf=batch_uf,
            company=company,
        ).first()

        if not batch:
            return Response(
                {"detail": "Batch not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Ensure range belongs to batch
        if (
            number_from < batch.number_from
            or number_to > batch.number_to
        ):
            return Response(
                {"detail": "Range outside batch"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from_holder = self._resolve_holder(
                holder_type=data.get("from_holder_type"),
                vehicle_uf=data.get("from_vehicle_uf"),
                customer_uf=data.get("from_customer_uf"),
            )

            to_holder = self._resolve_holder(
                holder_type=data.get("to_holder_type"),
                vehicle_uf=data.get("to_vehicle_uf"),
                customer_uf=data.get("to_customer_uf"),
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            from_holder is None
            and to_holder is None
        ):
            return Response(
                {"detail": "Source and destination must be different"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            from_holder is not None
            and to_holder is not None
            and from_holder.id == to_holder.id
        ):
            return Response(
                {"detail": "Source and destination must be different"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # -----------------------------
        # Availability check (CRITICAL)
        # -----------------------------
        unavailable = self._range_not_available(
            batch=batch,
            number_from=number_from,
            number_to=number_to,
            expected_holder=from_holder,
        )

        if unavailable:
            return Response(
                {"detail": "CMR range not available for source holder"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------
        # Create movement
        # -----------------------------
        movement = CMRStockMovement.objects.create(
            batch=batch,
            series=batch.series,
            number_from=number_from,
            number_to=number_to,
            movement_type=CMRStockMovement.TRANSFER,
            from_holder=from_holder,
            to_holder=to_holder,
            created_by=request.user,
        )

        return Response(
            {
                "status": "ok",
                "movement_uf": movement.id,
            },
            status=status.HTTP_201_CREATED,
        )

    # ======================================================
    # Helpers
    # ======================================================

    def _resolve_holder(self, holder_type, vehicle_uf=None, customer_uf=None):
        holder_type = (holder_type or "").strip().upper()

        if holder_type == "COMPANY":
            return None

        if holder_type == "VEHICLE":
            if not vehicle_uf:
                raise ValueError("vehicle_uf required")

            vehicle = Vehicle.objects.filter(uf=vehicle_uf).first()
            if not vehicle:
                raise ValueError("Vehicle not found")

            holder, _ = CMRHolder.objects.get_or_create(
                holder_type=CMRHolder.VEHICLE,
                vehicle=vehicle,
            )

            return holder

        if holder_type == "CUSTOMER":
            if not customer_uf:
                raise ValueError("customer_uf required")

            customer = Contact.objects.filter(uf=customer_uf).first()
            if not customer:
                raise ValueError("Customer not found")

            holder, _ = CMRHolder.objects.get_or_create(
                holder_type=CMRHolder.CUSTOMER,
                customer=customer,
            )

            return holder

        raise ValueError(f"Invalid holder_type: {holder_type}")

    def _range_not_available(self, batch, number_from, number_to, expected_holder):
        """
        Returns True if ANY number in range is not owned by expected_holder
        """
        movements = (
            batch.movements
            .filter(
                number_from__lte=number_to,
                number_to__gte=number_from,
            )
            .order_by("created_at")
        )

        for m in movements:
            # consumed = never available
            if m.movement_type == CMRStockMovement.CONSUMED:
                return True

            # transfer logic
            owner = m.to_holder
            if owner != expected_holder:
                return True

        return False


def _serialize_holder(holder):
    if not holder:
        return None

    if holder.vehicle:
        return {
            "vehicle": {
                "reg_number": holder.vehicle.reg_number,
                "uf": holder.vehicle.uf,
            }
        }

    if holder.customer:
        return {
            "customer": {
                "name": holder.customer.company_name,
                "uf": holder.customer.uf,
            }
        }

    return None


class CMRTransfersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = get_user_company(request.user)

        movements = (
            CMRStockMovement.objects
            .filter(
                movement_type=CMRStockMovement.TRANSFER,
                batch__company=company,
            )
            .select_related(
                "batch",
                "from_holder__vehicle",
                "from_holder__customer",
                "to_holder__vehicle",
                "to_holder__customer",
                "created_by",
            )
            .order_by("-created_at")
        )

        data = [
            {
                "id": m.id,
                "uf": m.uf,
                "created_at": m.created_at,
                "series": m.series,
                "number_from": m.number_from,
                "number_to": m.number_to,
                "quantity": m.quantity,
                "batch": {
                    "uf": m.batch.uf,
                    "series": m.batch.series,
                },
                "from_holder": _serialize_holder(m.from_holder),
                "to_holder": _serialize_holder(m.to_holder),
                "created_by": (
                    f"{m.created_by.first_name} {m.created_by.last_name}".strip()
                    if m.created_by and (m.created_by.first_name or m.created_by.last_name)
                    else (m.created_by.email if m.created_by else None)
                ),
            }
            for m in movements
        ]

        return Response(data)


def build_available_ranges(*, holder, role, company=None):
    results = []

    # ALWAYS start from company batches
    batches = CMRStockBatch.objects.filter(company=company)

    for batch in batches:
        movements = (
            batch.movements
            .order_by("created_at")
        )

        ownership = {}

        # init ownership = company
        for n in range(batch.number_from, batch.number_to + 1):
            ownership[n] = None  # None == COMPANY

        # replay movements
        for m in movements:
            for n in range(m.number_from, m.number_to + 1):
                if m.movement_type == CMRStockMovement.CONSUMED:
                    ownership[n] = "CONSUMED"
                else:
                    ownership[n] = m.to_holder

        # extract ranges owned by `holder`
        current_start = None

        for n in range(batch.number_from, batch.number_to + 2):
            owner = ownership.get(n)

            if owner == holder:
                if current_start is None:
                    current_start = n
            else:
                if current_start is not None:
                    results.append({
                        "batch_uf": batch.uf,
                        "series": batch.series,
                        "number_from": current_start,
                        "number_to": n - 1,
                        "quantity": (n - current_start),
                        "holder_type": role,
                    })
                    current_start = None

    return results


class CMRAvailableForLoadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        load_uf = request.query_params.get("load_uf")
        company = get_user_company(request.user)

        data = []

        # ---------------------------------
        # LOAD-SPECIFIC availability
        # ---------------------------------
        if load_uf:
            try:
                load = Load.objects.select_related(
                    "vehicle_tractor",
                    "vehicle_trailer",
                    "bill_to",
                ).get(uf=load_uf)
            except Load.DoesNotExist:
                return Response(
                    {"detail": "Load not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            holders = []

            if load.vehicle_tractor:
                holders.append(("TRACTOR", load.vehicle_tractor))

            if load.vehicle_trailer:
                holders.append(("TRAILER", load.vehicle_trailer))

            if load.bill_to:
                holders.append(("CUSTOMER", load.bill_to))

            for role, obj in holders:
                holder = CMRHolder.objects.filter(
                    vehicle=obj if role in ("TRACTOR", "TRAILER") else None,
                    customer=obj if role == "CUSTOMER" else None,
                ).first()

                if holder:
                    data += build_available_ranges(
                        holder=holder,
                        role=role,
                    )

        # ---------------------------------
        # COMPANY stock (always included)
        # ---------------------------------
        data += build_available_ranges(
            holder=None,
            role="COMPANY",
            company=company,
        )

        return Response(data)


class CMRConsumeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data

        batch_uf = data.get("batch_uf")
        number = data.get("number")
        holder_type = data.get("holder_type")
        holder_uf = data.get("holder_uf")
        load_uf = data.get("load_uf")

        if not all([batch_uf, number, load_uf]):
            return Response(
                {"detail": "batch_uf, number, load_uf are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            number = int(number)
        except (TypeError, ValueError):
            return Response(
                {"detail": "number must be integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = get_user_company(request.user)

        batch = CMRStockBatch.objects.filter(
            uf=batch_uf,
            company=company,
        ).first()

        if not batch:
            return Response({"detail": "Batch not found"}, status=404)

        load = Load.objects.filter(uf=load_uf).first()
        if not load:
            return Response({"detail": "Load not found"}, status=404)

        from_holder = None
        if holder_type == "VEHICLE":
            from_holder = CMRHolder.objects.filter(
                vehicle__uf=holder_uf).first()
        elif holder_type == "CUSTOMER":
            from_holder = CMRHolder.objects.filter(
                customer__uf=holder_uf).first()

        # Prevent double-consume
        if CMRStockMovement.objects.filter(
            batch=batch,
            number_from__lte=number,
            number_to__gte=number,
            movement_type=CMRStockMovement.CONSUMED,
        ).exists():
            return Response(
                {"detail": "CMR already consumed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        CMRStockMovement.objects.create(
            batch=batch,
            series=batch.series,
            number_from=number,
            number_to=number,
            movement_type=CMRStockMovement.CONSUMED,
            from_holder=from_holder,
            to_holder=None,
            load=load,
            created_by=request.user,
            notes=f"Consumed for load {load.uf}",
        )

        return Response({"status": "ok"}, status=status.HTTP_201_CREATED)

###### END CMR TRANSFER ######
