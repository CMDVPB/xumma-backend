import os
import uuid
from pathlib import Path
from rest_framework import generics, permissions
from django.conf import settings
from django.utils.dateparse import parse_date, parse_datetime
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView

from ayy.services.fuel_sync import fifo_price_preview
from .serializers import FuelPreviewSerializer, FuelTankUpdateSerializer, ImportBatchListSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from .tasks import match_unmatched_import_rows_all_companies, process_import_batch
from .models import ImportBatch, SupplierFormat, FuelTank, TankRefill, TruckFueling
from .serializers import ImportCreateSerializer, ImportBatchDetailSerializer, FuelTankSerializer, TankRefillCreateSerializer, \
    TankRefillListSerializer, TankRefillUpdateSerializer, TruckFuelingCreateSerializer


class ImportSuppliersView(APIView):
    def get(self, request):
        user_company = get_user_company(request.user)

        suppliers = (
            SupplierFormat.objects
            .filter(company=user_company, is_active=True)
            .select_related("supplier")
        )

        return Response([
            {
                "uf": sf.supplier.uf,
                "company_name": sf.supplier.company_name,
            }
            for sf in suppliers
        ])


class CostImportCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        print(request.content_type)
        print(request.data)

        serializer = ImportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = get_user_company(request.user)
        supplier_uf = serializer.validated_data["supplier_uf"]

        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"detail": "No files uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        supplier_format = get_object_or_404(
            SupplierFormat,
            company=company,
            supplier__uf=supplier_uf,
            is_active=True,
        )

        batch = ImportBatch.objects.create(
            company=company,
            supplier=supplier_format.supplier,
            period_from=serializer.validated_data["period_from"],
            period_to=serializer.validated_data["period_to"],
            created_by=request.user,
        )

        # file_paths = []
        # for f in files:
        #     tmp_file = tempfile.NamedTemporaryFile(
        #         delete=False,
        #         suffix=f"_{f.name}"
        #     )

        #     for chunk in f.chunks():
        #         tmp_file.write(chunk)

        #     tmp_file.close()

        #     file_paths.append(tmp_file.name)

        # UPLOAD_DIR = "/uploads"

        # file_paths = []

        # for f in files:
        #     filename = f"{uuid.uuid4()}_{f.name}"
        #     path = os.path.join(UPLOAD_DIR, filename)

        #     with open(path, "wb+") as dest:
        #         for chunk in f.chunks():
        #             dest.write(chunk)

        #     file_paths.append(path)

        upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_paths = []

        for f in files:
            filename = f"{uuid.uuid4()}_{f.name}"
            path = upload_dir / filename

            with open(path, "wb+") as dest:
                for chunk in f.chunks():
                    dest.write(chunk)

            file_paths.append(str(path))

        process_import_batch.delay(
            batch_id=batch.id,
            supplier_format_id=supplier_format.id,
            file_paths=file_paths,
        )

        return Response(
            {
                "uf": batch.uf,
                "status": batch.status,
                "year": batch.year,
                "sequence": batch.sequence,
            },
            status=status.HTTP_201_CREATED,
        )


class CostImportListView(ListAPIView):
    serializer_class = ImportBatchListSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return (ImportBatch.objects
                .filter(
                    company=user_company
                )
                .order_by(
                    "-created_at"
                ))


class CostImportDetailView(RetrieveAPIView):
    serializer_class = ImportBatchDetailSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return ImportBatch.objects.filter(
            company=user_company
        )


class RerunCostMatchingView(APIView):
    """
    Triggers re-matching of unmatched import rows to trips.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            days_back = int(request.data.get("days_back", 30))
        except (TypeError, ValueError):
            days_back = 30

        # Safety limits
        days_back = max(1, min(days_back, 365))

        match_unmatched_import_rows_all_companies.delay(days_back)

        return Response(
            {
                "status": "started",
                "days_back": days_back,
            },
            status=status.HTTP_202_ACCEPTED,
        )

###### START FUEL & ADBLUE ######


class FuelTankListView(generics.ListAPIView):
    serializer_class = FuelTankSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return FuelTank.objects.filter(
            company=user_company
        )


class FuelTankDetailView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FuelTankUpdateSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return FuelTank.objects.filter(
            company=get_user_company(self.request.user)
        )

    def perform_update(self, serializer):
        tank = self.get_object()

        new_capacity = serializer.validated_data["capacity_l"]
        current_stock = tank.get_current_fuel_stock()

        if new_capacity < current_stock:
            raise ValidationError(
                "Capacity cannot be lower than current fuel stock"
            )

        serializer.save()


FUEL_CODE_TO_TYPE = {
    "adblue_tanc": FuelTank.FUEL_ADBLUE,
    "dt_tanc": FuelTank.FUEL_DIESEL,
}


class FuelPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FuelPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fuel_code = serializer.validated_data["fuel_code"]
        quantity_l = serializer.validated_data["quantity_l"]

        fuel_type = FUEL_CODE_TO_TYPE.get(fuel_code)
        if not fuel_type:
            return Response(
                {"detail": "Invalid fuel code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = get_user_company(request.user)

        try:
            tank = FuelTank.objects.get(
                company=company,
                fuel_type=fuel_type,
            )
        except FuelTank.DoesNotExist:
            return Response(
                {"detail": "Fuel tank not configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = fifo_price_preview(
                tank=tank,
                quantity_l=quantity_l,
            )
        except ValidationError:
            return Response(
                {"detail": "Not enough fuel in tank"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        currency_code = None

        company = tank.company

        if hasattr(company, "company_settings") and company.company_settings.currency:
            currency_code = company.company_settings.currency.currency_code

        return Response(
            {
                "price_per_l": result["price_per_l"],
                "total_cost": result["total_cost"],
                "currency": currency_code,
            },
            status=status.HTTP_200_OK,
        )


class TankRefillCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TankRefillCreateSerializer


class TruckFuelingCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TruckFuelingCreateSerializer


class TankRefillListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TankRefillListSerializer

    def get_queryset(self):
        start_date_raw = self.request.query_params.get("start_date")
        end_date_raw = self.request.query_params.get("end_date")

        start_date = None
        end_date = None

        if start_date_raw:
            start_date = (
                parse_date(start_date_raw)
                or parse_datetime(start_date_raw).date()
            )

        if end_date_raw:
            end_date = (
                parse_date(end_date_raw)
                or parse_datetime(end_date_raw).date()
            )

        user_company = get_user_company(self.request.user)

        qs = (
            TankRefill.objects
            .filter(tank__company=user_company)
            .select_related(
                "tank",
                "supplier",
                "vehicle",
                "person"
            )
            .prefetch_related(
                "supplier__contact_vehicle_units",
                "supplier__contact_persons",
            )
        )

        if start_date:
            qs = qs.filter(date__date__gte=start_date)

        if end_date:
            qs = qs.filter(date__date__lte=end_date)

        return qs.order_by("-date")


class TankRefillDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TankRefillUpdateSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return TankRefill.objects.filter(
            tank__company=get_user_company(self.request.user)
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = self.get_object()
            tank = (
                FuelTank.objects
                .select_for_update()
                .get(id=instance.tank_id)
            )

            # simulate new values
            old_qty = instance.actual_quantity_l
            new_qty = serializer.validated_data.get(
                "actual_quantity_l", old_qty
            )

            current_stock = tank.get_current_fuel_stock(using_actual=True)
            delta = new_qty - old_qty

            if delta > 0 and current_stock + delta > tank.capacity_l:
                raise ValidationError("Tank capacity exceeded")

            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            tank = (
                FuelTank.objects
                .select_for_update()
                .get(id=instance.tank_id)
            )

            current_stock = tank.get_current_fuel_stock(using_actual=True)

            if instance.actual_quantity_l > current_stock:
                raise ValidationError(
                    "Cannot delete refill: fuel already used")

            instance.delete()


class TruckFuelingListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = (TruckFueling.objects
              .filter(tank__company=user_company)
              .select_related(
                  "tank",
                  "vehicle",
                  "driver"
              )
              .order_by(
                  "-fueled_at")
              )

        return qs


###### END FUEL & ADBLUE ######
