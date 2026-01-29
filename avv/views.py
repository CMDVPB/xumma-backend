from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, Q, Value, Count
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.filters import SearchFilter, OrderingFilter

from abb.models import Currency
from abb.utils import get_user_company
from avv.serializers_driver_reports import DriverReportCreateSerializer, DriverReportDetailsSerializer, DriverReportListSerializer

from .models import DriverReport, IssueDocument, Location, Part, PartRequest, StockBalance, StockLot, StockMovement, UnitOfMeasure, Warehouse, WorkOrder, WorkOrderIssue, WorkType
from .serializers import (
    IssueDocumentDetailSerializer,
    IssueDocumentListSerializer,
    LocationByPartSerializer,
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
    WorkOrderCreateSerializer,
    WorkOrderDetailSerializer,
    WorkOrderIssueSerializer,
    WorkOrderListSerializer,
    WorkOrderWorkLineCreateSerializer,
    WorkTypeCreateSerializer,
    WorkTypeSerializer,
)
from .services import confirm_issue_document, create_work_order_from_driver_report, issue_from_work_order, receive_stock, reserve_request, issue_request, InventoryError, start_work_order, transfer_stock


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

        currency_code = data.get("currency", "MDL")

        currency = Currency.objects.filter(
            currency_code=currency_code
        ).first()

        with transaction.atomic():
            # 1️⃣ Create LOT
            lot = StockLot.objects.create(
                company=company,
                created_by=request.user,
                part=data["part"],
                supplier_name=data.get("supplier_name", ""),
                unit_cost=data.get("unit_cost", 0),
                currency=currency,
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
                currency=currency,
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


class IssueDocumentListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = IssueDocumentListSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = (
            IssueDocument.objects
            .select_related("mechanic", "vehicle", "driver")
            .filter(company=company)

        )
        return qs.order_by("-created_at")


class IssueDocumentDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = IssueDocumentDetailSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = IssueDocument.objects.filter(company=company)
        return qs


class IssueDocumentConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        doc = confirm_issue_document(
            doc_id=pk,
            actor_user=request.user,
        )
        return Response(
            {"status": doc.status},
            status=status.HTTP_200_OK,
        )


class WorkOrderListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return WorkOrder.objects.filter(company=company)

    def get_serializer_class(self):
        return WorkOrderListSerializer

    def perform_create(self, serializer):
        serializer.save(
            company=get_user_company(self.request.user),
            created_by=self.request.user,
        )


class WorkOrderIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        work_order = get_object_or_404(WorkOrder.objects.select_for_update(),
                                       id=pk,
                                       )
        part = get_object_or_404(Part.objects.select_for_update(),
                                 id=request.data["part"],
                                 )
        location = get_object_or_404(Location.objects.select_for_update(),
                                     id=request.data["location"],
                                     )
        issue_from_work_order(
            work_order=work_order,
            part=part,
            location=location,
            qty=Decimal(request.data["qty"]),
            issued_by=request.user,
        )
        return Response({"status": "ok"})


class WorkOrderIssueListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkOrderIssueSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return WorkOrderIssue.objects.filter(
            company=company,
            work_order_id=self.kwargs["pk"],
        )


class WorkOrderCreateView(generics.CreateAPIView):
    serializer_class = WorkOrderCreateSerializer
    queryset = WorkOrder.objects.all()

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(
            company=user_company,
            created_by=self.request.user,
            status=WorkOrder.Status.DRAFT,
        )


class WorkOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkOrderDetailSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return WorkOrder.objects.filter(company=company)


class LocationsByPartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        part_id = request.query_params.get("part")

        if not part_id:
            return Response(
                {"detail": "part query parameter is required"},
                status=400,
            )

        company = get_user_company(request.user)

        balances = (
            StockBalance.objects
            .filter(
                company=company,
                part_id=part_id,
                qty_on_hand__gt=0,
            )
            .select_related("location", "lot")
            .annotate(
                qty_available=F("qty_on_hand") - F("qty_reserved"),
                location_name=F("location__name"),
                lot_code=Coalesce(F("lot__code"), Value(None)),
            )
            .filter(qty_available__gt=0)
            .values(
                "id",
                "location_id",
                "location_name",
                "lot_id",
                "lot_code",
                "qty_on_hand",
                "qty_reserved",
                "qty_available",
            )
        )

        data = [
            {
                "balance_id": b["id"],
                "location_id": b["location_id"],
                "location_name": b["location_name"],
                "lot_id": b["lot_id"],
                "lot_code": b["lot_code"],
                "qty_on_hand": b["qty_on_hand"],
                "qty_reserved": b["qty_reserved"],
                "qty_available": b["qty_available"],
            }
            for b in balances
        ]

        return Response(data)


class WorkOrderStartView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        work_order = get_object_or_404(
            WorkOrder.objects.select_for_update(),
            pk=pk,
            company=get_user_company(request.user),
        )

        try:
            start_work_order(
                work_order=work_order,
                actor_user=request.user,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WorkOrderDetailSerializer(work_order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkOrderCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        work_order = get_object_or_404(
            WorkOrder.objects.select_for_update(),
            pk=pk,
        )

        # ✅ Status check
        if work_order.status != WorkOrder.Status.IN_PROGRESS:
            return Response(
                {"detail": "Only IN_PROGRESS work orders can be completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Permission check
        if work_order.mechanic_id != request.user.id:
            return Response(
                {"detail": "Only assigned mechanic can complete this work order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ✅ Transition
        work_order.status = WorkOrder.Status.COMPLETED
        work_order.completed_at = timezone.now()
        work_order.save(update_fields=["status", "completed_at"])

        return Response(
            WorkOrderDetailSerializer(work_order).data,
            status=status.HTTP_200_OK,
        )


class LocationsByPartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, part_id):
        company = get_user_company(request.user)

        if not Part.objects.filter(id=part_id, company=company).exists():
            return Response(
                {"detail": "Part not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        balances = (
            StockBalance.objects
            .filter(
                company=company,
                part_id=part_id,
                qty_on_hand__gt=0,
            )
            .select_related("location")
        )

        data = [
            {
                "location_id": b.location.id,
                "location_name": b.location.name,
                "qty_on_hand": b.qty_on_hand,
                "qty_available": b.qty_available,  # ✅ property
            }
            for b in balances
            if b.qty_available > 0
        ]

        serializer = LocationByPartSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkTypeCreateView(CreateAPIView):
    serializer_class = WorkTypeCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        serializer.save(company=company)


class WorkTypeListView(ListAPIView):
    serializer_class = WorkTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return WorkType.objects.filter(company=company)


class WorkOrderWorkLineCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        wo = get_object_or_404(
            WorkOrder.objects.select_for_update(),
            pk=pk,
            company=get_user_company(request.user),
        )

        # if not can_add_work_line(request.user, wo):
        #     raise PermissionDenied()

        serializer = WorkOrderWorkLineCreateSerializer(
            data=request.data,
            context={"work_order": wo},
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(
            work_order=wo,
            company=wo.company,
            created_by=request.user,
        )

        return Response(serializer.data, status=201)


class DriverReportCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriverReportCreateSerializer


class DriverReportSendView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        user = request.user
        company = get_user_company(user)

        report = get_object_or_404(
            DriverReport,
            pk=pk,
            company=company,
            driver=user,
        )

        if report.status != DriverReport.Status.DRAFT:
            return Response(
                {"detail": "Only DRAFT reports can be sent"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report.status = DriverReport.Status.SENT
        report.save(update_fields=["status"])

        return Response(
            {"status": report.status},
            status=status.HTTP_200_OK,
        )


class MyDriverReportListView(generics.ListAPIView):
    serializer_class = DriverReportListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        company = get_user_company(user)

        return (
            DriverReport.objects
            .filter(company=company, driver=user)
            .select_related("vehicle")
            .prefetch_related("report_driver_report_images")
            .order_by("-created_at")
        )


class DriverReportManagerListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriverReportListSerializer

    def get_queryset(self):

        company = get_user_company(self.request.user)
        qs = (
            DriverReport.objects
            .filter(company=company)
            .annotate(images_count=Count("report_driver_report_images"))
            .select_related("vehicle", "driver", "related_work_order", "reviewed_by")
            .order_by("-created_at")
        )

        p = self.request.query_params

        # optional filters
        if p.get("date_from"):
            qs = qs.filter(created_at__date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(created_at__date__lte=p["date_to"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("vehicle"):
            qs = qs.filter(vehicle_id=p["vehicle"])
        if p.get("driver"):
            qs = qs.filter(driver_id=p["driver"])

        return qs


class DriverReportManagerDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriverReportDetailsSerializer

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return DriverReport.objects.filter(company=company).select_related(
            "vehicle", "driver", "related_work_order", "reviewed_by"
        )


class DriverReportMarkReviewedView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):

        company = get_user_company(request.user)

        report = get_object_or_404(DriverReport, pk=pk, company=company)

        if report.status not in [DriverReport.Status.SENT]:
            return Response(
                {"detail": "Only SENT reports can be marked as reviewed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report.status = DriverReport.Status.REVIEWED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response({"status": report.status}, status=status.HTTP_200_OK)


class DriverReportRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = get_user_company(request.user)

        report = get_object_or_404(DriverReport, pk=pk, company=company)

        if report.status in [DriverReport.Status.CLOSED, DriverReport.Status.REJECTED]:
            return Response({"detail": "Already closed."}, status=400)

        report.status = DriverReport.Status.REJECTED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response({"status": report.status}, status=status.HTTP_200_OK)


class DriverReportCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = get_user_company(request.user)

        report = get_object_or_404(DriverReport, pk=pk, company=company)

        if report.status == DriverReport.Status.REJECTED:
            return Response({"detail": "Rejected reports cannot be closed."}, status=400)

        report.status = DriverReport.Status.CLOSED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response({"status": report.status}, status=status.HTTP_200_OK)


class DriverReportCreateWorkOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        try:
            wo = create_work_order_from_driver_report(
                report_id=pk,
                actor_user=request.user,
            )
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"work_order_id": wo.id},
            status=status.HTTP_201_CREATED,
        )
