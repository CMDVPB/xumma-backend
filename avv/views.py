from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.filters import SearchFilter, OrderingFilter

from abb.utils import get_user_company

from .models import Location, Part, PartRequest, StockBalance, StockLot, StockMovement, UnitOfMeasure, Warehouse
from .serializers import (
    LocationSerializer,
    PartRequestCreateSerializer,
    PartRequestListSerializer,
    PartRequestReadSerializer,
    PartRequestSerializer,
    PartSerializer,
    PartStockSerializer,
    StockBalanceSerializer,
    IssueDocumentSerializer,
    StockMovementSerializer,
    StockReceiveSerializer,
    UnitOfMeasureSerializer,
    WarehouseSerializer,
)
from .services import receive_stock, reserve_request, issue_request, InventoryError, transfer_stock


class UnitOfMeasureListView(ListAPIView):
    serializer_class = UnitOfMeasureSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = (UnitOfMeasure.objects
              .filter(
                  Q(company=company) |
                  Q(is_system=True),
                  is_active=True,
              )
              )
        return qs


class StockListView(generics.ListAPIView):
    serializer_class = PartStockSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)

        qs = (
            Part.objects
            .filter(company=company, is_active=True)
            .annotate(
                stock=Sum("part_stock_balances__qty_on_hand")
            )
            .order_by("-updated_at")
        )

        # Optional low-stock filter
        if self.request.query_params.get("low"):
            qs = qs.filter(stock__lte=F("min_level"))

        return qs


class StockBalanceListView(generics.ListAPIView):
    serializer_class = StockBalanceSerializer

    def get_queryset(self):
        qs = StockBalance.objects.select_related(
            "part", "location", "location__warehouse")
        part_id = self.request.query_params.get("part")
        warehouse_id = self.request.query_params.get("warehouse")

        if part_id:
            qs = qs.filter(part_id=part_id)
        if warehouse_id:
            qs = qs.filter(location__warehouse_id=warehouse_id)

        return qs


class PartListView(ListAPIView):
    serializer_class = PartSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'sku']

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = Part.objects.filter(
            company=user_company,
            is_active=True
        )
        return qs.order_by('name')


class PartCreateView(generics.CreateAPIView):
    serializer_class = PartSerializer

    def perform_create(self, serializer):
        serializer.save(
            company=get_user_company(self.request.user),
            created_by=self.request.user,
        )


class PartDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PartSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = (Part.objects
              .filter(
                  company=user_company,
                  is_active=True,
              ))
        return qs

    def perform_destroy(self, instance):
        # 🔒 soft delete (recommended)
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class PartRequestListCreateView(ListCreateAPIView):
    queryset = PartRequest.objects.all()
    serializer_class = PartRequestSerializer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PartRequestCreateSerializer
        return PartRequestListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user_company = get_user_company(self.request.user)
        return qs.filter(company=user_company)


class PartRequestDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PartRequestReadSerializer
    queryset = PartRequest.objects.select_related("vehicle", "mechanic", "driver").prefetch_related(
        "request_part_request_lines",
        "request_part_request_lines__part",
    )


class ReserveRequestView(APIView):
    def post(self, request, pk: int):
        try:
            req = reserve_request(
                request_id=pk,
                actor_user=request.user,
                warehouse_id=request.data.get("warehouse_id"),
            )
        except InventoryError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            PartRequestReadSerializer(req).data,
            status=status.HTTP_200_OK,
        )


class IssueRequestView(APIView):
    def post(self, request, pk: int):
        try:
            doc = issue_request(request_id=pk, actor_user=request.user)
        except InventoryError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            IssueDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class StockReceiveView(APIView):
    def post(self, request):
        serializer = StockReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        company = get_user_company(request.user)

        with transaction.atomic():
            # 1️⃣ Create LOT
            lot = StockLot.objects.create(
                company=company,
                created_by=request.user,
                part=data["part"],
                supplier_name=data.get("supplier_name", ""),
                unit_cost=data.get("unit_cost", 0),
                currency=data.get("currency", "EUR"),
                received_at=data.get("received_at") or timezone.now(),
            )

            # 2️⃣ Stock balance (lock row if exists)
            balance, _ = StockBalance.objects.select_for_update().get_or_create(
                company=company,
                part=data["part"],
                location=data["location"],
                lot=lot,
                defaults={
                    "qty_on_hand": 0,
                    "qty_reserved": 0,
                },
            )

            balance.qty_on_hand += data["qty"]
            balance.save(update_fields=["qty_on_hand"])

            # 3️⃣ Movement ledger
            StockMovement.objects.create(
                company=company,
                created_by=request.user,
                type=StockMovement.Type.RECEIPT,
                part=data["part"],
                lot=lot,
                to_location=data["location"],
                qty=data["qty"],
                unit_cost_snapshot=data.get("unit_cost", 0),
                currency=data.get("currency", "EUR"),
                ref_type="RECEIPT",
                ref_id=str(lot.id),
            )

        return Response(
            {
                "status": "ok",
                "lot_id": lot.id,
                "qty_received": str(data["qty"]),
            },
            status=status.HTTP_201_CREATED,
        )


class StockMovementListView(ListAPIView):
    serializer_class = StockMovementSerializer
    filter_backends = [OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = (
            StockMovement.objects
            .select_related(
                "part",
                "lot",
                "from_location__warehouse",
                "to_location__warehouse",
            )
            .filter(company=company)
        )

        p = self.request.query_params

        if p.get("part"):
            qs = qs.filter(part_id=p["part"])

        if p.get("type"):
            qs = qs.filter(type=p["type"])

        if p.get("date_from"):
            qs = qs.filter(created_at__date__gte=parse_date(p["date_from"]))

        if p.get("date_to"):
            qs = qs.filter(created_at__date__lte=parse_date(p["date_to"]))

        return qs


class WarehouseListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WarehouseSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = Warehouse.objects.filter(company=company)
        return qs.order_by("code")


class LocationListView(ListAPIView):
    serializer_class = LocationSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        warehouse_id = self.request.query_params.get("warehouse")

        qs = Location.objects.filter(
            company=company,
        ).select_related("warehouse")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        return qs.order_by("code")


class StockTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = get_user_company(request.user)
        data = request.data

        try:
            result = transfer_stock(
                balance_id=int(data["balance_id"]),
                to_location_id=int(data["to_location"]),
                qty=Decimal(data["qty"]),
                company=company,
                user=request.user,
            )
        except KeyError:
            return Response(
                {"detail": "balance_id, to_location and qty are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_200_OK)
