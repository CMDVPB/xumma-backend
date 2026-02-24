import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from app.models import LoadWarehouse
from axx.models import Load, LoadMovement, Trip
from cwh.serializers import BulkUnloadSerializer, LoadReloadSerializer, LoadUnloadSerializer, LoadWarehouseListSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class LoadWarehouseListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadWarehouseListSerializer

    def get_queryset(self):

        user_company = get_user_company(self.request.user)

        if not user_company:
            return LoadWarehouse.objects.none()

        qs = LoadWarehouse.objects.filter(company=user_company)

        active = self.request.query_params.get("active", "1")
        if active in ("1", "true", "True", "yes"):
            qs = qs.filter(is_active=True)

        return qs.select_related("country_warehouse").order_by("name_warehouse")


class LoadUnloadToWarehouseView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadUnloadSerializer

    def post(self, request, load_uf):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        warehouse_id = serializer.validated_data["warehouse_id"]

        with transaction.atomic():

            try:
                load = (
                    Load.objects
                    .select_for_update()
                    .select_related("warehouse", "trip", "company")
                    .get(uf=load_uf)
                )
            except Load.DoesNotExist:
                raise NotFound("Load not found.")

            if load.location_type != "trip":
                raise ValidationError("Load is not currently on a trip.")

            if load.location_type == "delivered":
                raise ValidationError("Delivered loads cannot be unloaded.")

            try:
                warehouse = LoadWarehouse.objects.get(pk=warehouse_id)
            except LoadWarehouse.DoesNotExist:
                raise NotFound("Warehouse not found.")

            if warehouse.company_id != load.company_id:
                raise ValidationError("Invalid warehouse for this load.")

            # State transition

            load.location_type = "warehouse"
            load.warehouse = warehouse
            load.save()

            # Movement history

            LoadMovement.objects.create(
                load=load,
                from_location="trip",
                to_location="warehouse",
                warehouse=warehouse
            )

        return Response({"status": "unloaded"}, status=status.HTTP_200_OK)


class BulkUnloadLoadsToWarehouseView(GenericAPIView):
    """
    POST /api/loads/bulk-unload-to-warehouse/
    body: { "load_ufs": ["...","..."], "warehouse_id": 123 }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BulkUnloadSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_company = get_user_company(request.user)
        if not user_company:
            raise ValidationError("User has no company.")

        load_ufs = serializer.validated_data["load_ufs"]
        warehouse = get_object_or_404(
            LoadWarehouse,
            id=serializer.validated_data["warehouse_id"],
            company=user_company,
        )

        unloaded = []
        failed = []

        with transaction.atomic():
            loads = list(
                Load.objects.select_for_update()
                .filter(company=user_company, uf__in=load_ufs)
            )

            found_ufs = {l.uf for l in loads}
            missing = [uf for uf in load_ufs if uf not in found_ufs]
            for uf in missing:
                failed.append({"uf": uf, "reason": "not_found"})

            for load in loads:
                if load.location_type != "trip":
                    failed.append({"uf": load.uf, "reason": "not_on_trip"})
                    continue

                load.location_type = "warehouse"
                load.warehouse = warehouse
                load.save(update_fields=["location_type", "warehouse", "trip"])

                LoadMovement.objects.create(
                    load=load,
                    from_location="trip",
                    to_location="warehouse",
                    warehouse=warehouse,
                )

                unloaded.append(load.uf)

        return Response(
            {"unloaded": len(unloaded), "unloaded_ufs": unloaded,
             "failed": failed},
            status=status.HTTP_200_OK,
        )


class LoadReloadToTripView(GenericAPIView):
    serializer_class = LoadReloadSerializer

    def post(self, request, load_uf):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trip_id = serializer.validated_data["trip_id"]

        with transaction.atomic():

            try:
                load = (
                    Load.objects
                    .select_for_update()
                    .select_related("warehouse", "trip", "company")
                    .get(uf=load_uf)
                )
            except Load.DoesNotExist:
                raise NotFound("Load not found.")

            if load.location_type != "warehouse":
                raise ValidationError("Load is not in a warehouse.")

            if load.location_type == "delivered":
                raise ValidationError("Delivered loads cannot be reloaded.")

            try:
                trip = (
                    Trip.objects
                    .select_for_update()
                    .select_related("company")
                    .get(pk=trip_id)
                )
            except Trip.DoesNotExist:
                raise NotFound("Trip not found.")

            if trip.company_id != load.company_id:
                raise ValidationError("Trip and Load company mismatch.")

            if load.trip_id == trip.id:
                raise ValidationError("Load already assigned to this trip.")

            # State transition

            previous_warehouse = load.warehouse

            load.location_type = "trip"
            load.trip = trip
            load.warehouse = None
            load.save()

            # Movement history

            LoadMovement.objects.create(
                load=load,
                from_location="warehouse",
                to_location="trip",
                trip=trip,
                warehouse=previous_warehouse
            )

        return Response({"status": "reloaded"}, status=status.HTTP_200_OK)
