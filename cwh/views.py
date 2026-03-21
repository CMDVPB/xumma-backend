import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, OuterRef, Subquery, DateTimeField, Exists, CharField, Sum, Value, IntegerField, FloatField
from django.db.models.functions import Coalesce, Cast, NullIf
from django.shortcuts import get_object_or_404

from abb.utils import get_user_company
from app.models import LoadWarehouse
from axx.models import Load, LoadMovement, Trip
from cwh.serializers import (BulkUnloadSerializer, LoadArriveToWarehouseSerializer, LoadReloadSerializer, LoadUnloadSerializer, LoadWarehouseCreateSerializer,
                             LoadWarehouseDetailSerializer, LoadWarehouseListSerializer, WarehouseLoadListSerializer)

logger = logging.getLogger(__name__)

User = get_user_model()


class LoadWarehouseListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadWarehouseListSerializer

    def get_queryset(self):

        user_company = get_user_company(self.request.user)

        if not user_company:
            return LoadWarehouse.objects.none()

        qs = LoadWarehouse.objects.filter(company=user_company).annotate(
                loads_count=Count(
                    "warehouse_loads",
                    filter=Q(warehouse_loads__location_type="warehouse"),
                    distinct=True,
                ),
                loads_expected_count=Count(
                    "warehouse_load_movements__load",
                    filter=Q(warehouse_load_movements__status="expected_warehouse"),
                    distinct=True,
                ),
                loads_arrived_count=Count(
                    "warehouse_load_movements__load",
                    filter=Q(warehouse_load_movements__status="arrived_warehouse"),
                    distinct=True,
                ),
        )

        active = self.request.query_params.get("active", "1")
        if active in ("1", "true", "True", "yes"):
            qs = qs.filter(is_active=True)

        qs = qs.select_related("country_warehouse")

        return qs.order_by("name_warehouse")


class SingleUnloadToWarehouseView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadUnloadSerializer

    def post(self, request, load_uf):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        warehouse_uf = serializer.validated_data["warehouse_uf"]
        movement_status = serializer.validated_data["movement_status"]

        user_company = get_user_company(request.user)
        if not user_company:
            raise ValidationError("User has no company.")

        with transaction.atomic():
            try:
                load = (
                    Load.objects
                    .select_for_update()
                    .select_related("warehouse", "trip", "company")
                    .get(uf=load_uf, company=user_company)
                )
            except Load.DoesNotExist:
                raise NotFound("Load not found.")

            if load.location_type == "delivered":
                raise ValidationError("Delivered loads cannot be moved to warehouse.")

            if load.location_type not in ["trip", "warehouse"]:
                raise ValidationError("Load cannot be moved to warehouse from its current state.")

            try:
                warehouse = LoadWarehouse.objects.get(
                    uf=warehouse_uf,
                    company=user_company,
                )
            except LoadWarehouse.DoesNotExist:
                raise NotFound("Warehouse not found.")

            changed_fields = []

            if load.warehouse_id != warehouse.id:
                load.warehouse = warehouse
                changed_fields.append("warehouse")

            if load.location_type != "warehouse":
                load.location_type = "warehouse"
                changed_fields.append("location_type")

            if changed_fields:
                load.save(update_fields=changed_fields)

            if movement_status == "arrived_warehouse":
                LoadMovement.objects.filter(
                    load=load,
                    warehouse=warehouse,
                    status="expected_warehouse",
                ).delete()

            LoadMovement.objects.create(
                load=load,
                trip=load.trip,
                from_location="trip" if load.trip_id else "unknown",
                to_location="warehouse",
                warehouse=warehouse,
                status=movement_status,
            )

        return Response(
            {
                "status": "ok",
                "movement_status": movement_status,
                "load_uf": load.uf,
                "warehouse": {
                    "uf": warehouse.uf,
                    "name_warehouse": warehouse.name_warehouse,
                },
            },
            status=status.HTTP_200_OK,
        )


class BulkUnloadLoadsToWarehouseView(GenericAPIView):
    """
    POST /api/loads/bulk-unload-to-warehouse/

    body:
    {
        "load_ufs": ["...","..."],
        "warehouse_uf": "...",
        "movement_status": "expected_warehouse" | "arrived_warehouse"
    }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BulkUnloadSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        warehouse_uf = serializer.validated_data["warehouse_uf"]

        print('2274', warehouse_uf)

        user_company = get_user_company(request.user)
        if not user_company:
            raise ValidationError("User has no company.")

        load_ufs = serializer.validated_data["load_ufs"]


        warehouse = get_object_or_404(
            LoadWarehouse,
            uf=warehouse_uf,
            company=user_company,
        )
        movement_status = serializer.validated_data["movement_status"]

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
                if load.location_type not in ["trip", "warehouse"]:
                    failed.append({"uf": load.uf, "reason": "invalid_location_type"})
                    continue

                update_fields = []

                # expected -> visible in warehouse page, but not yet arrived
                if movement_status == "expected_warehouse":
                    if load.warehouse_id != warehouse.id:
                        load.warehouse = warehouse
                        update_fields.append("warehouse")

                    if load.location_type != "warehouse":
                        load.location_type = "warehouse"
                        update_fields.append("location_type")

                # arrived -> definitely in warehouse
                elif movement_status == "arrived_warehouse":
                    if load.warehouse_id != warehouse.id:
                        load.warehouse = warehouse
                        update_fields.append("warehouse")

                    if load.location_type != "warehouse":
                        load.location_type = "warehouse"
                        update_fields.append("location_type")

                if update_fields:
                    load.save(update_fields=update_fields)

                # remove stale expected movement for same load+warehouse before insert arrived
                if movement_status == "arrived_warehouse":
                    LoadMovement.objects.filter(
                        load=load,
                        warehouse=warehouse,
                        status="expected_warehouse",
                    ).delete()

                LoadMovement.objects.create(
                    load=load,
                    trip=load.trip,
                    from_location="trip",
                    to_location="warehouse",
                    warehouse=warehouse,
                    status=movement_status,
                )

                unloaded.append(load.uf)

        return Response(
            {
                "updated": len(unloaded),
                "updated_ufs": unloaded,
                "failed": failed,
            },
            status=status.HTTP_200_OK,
        )


class LoadReloadToTripView(GenericAPIView):
    serializer_class = LoadReloadSerializer

    def post(self, request, load_uf):
        from driver.views import sync_trip_stops_for_trip

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


            sync_trip_stops_for_trip(trip)
            trip.stops_version += 1
            trip.save(update_fields=["stops_version"])

            # Movement history

            LoadMovement.objects.create(
                load=load,
                from_location="warehouse",
                to_location="trip",
                trip=trip,
                warehouse=previous_warehouse
            )

        return Response({"status": "reloaded"}, status=status.HTTP_200_OK)


class LoadWarehouseCreateView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadWarehouseCreateSerializer

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if not company:
            raise ValidationError("User has no company.")
        serializer.save(company=company)

###### START LOADS IN THE WAREHOUSE ######

class LoadWarehouseDetailView(RetrieveAPIView):
    """
    GET /api/load-warehouses/<warehouseUf>/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LoadWarehouseDetailSerializer
    lookup_field = "uf"
    lookup_url_kwarg = "warehouseUf"

    def get_queryset(self):
        company = get_user_company(self.request.user)
        if not company:
            return LoadWarehouse.objects.none()

        return (
            LoadWarehouse.objects.filter(company=company)
            .select_related("country_warehouse")
            .annotate(
                loads_count=Count(
                    "warehouse_loads__id",
                    filter=Q(warehouse_loads__location_type="warehouse"),
                    distinct=True,
                )
            )
        )


class WarehouseLoadListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WarehouseLoadListSerializer

    def get_warehouse(self):
        company = get_user_company(self.request.user)
        if not company:
            raise ValidationError("User has no company.")

        return get_object_or_404(
            LoadWarehouse.objects.filter(company=company),
            uf=self.kwargs["warehouseUf"],
        )

    def get_queryset(self):
        company = get_user_company(self.request.user)
        if not company:
            return Load.objects.none()

        warehouse = self.get_warehouse()
        location_type = self.request.query_params.get("location_type", "warehouse")
        q = (self.request.query_params.get("q") or "").strip()

        latest_movement_qs = LoadMovement.objects.filter(
            load_id=OuterRef("pk"),
            warehouse=warehouse,
        ).order_by("-date")

        latest_status_subq = latest_movement_qs.values("status")[:1]
        latest_arrived_subq = LoadMovement.objects.filter(
            load_id=OuterRef("pk"),
            warehouse=warehouse,
            status="arrived_warehouse",
        ).order_by("-date").values("date")[:1]

        qs = Load.objects.filter(company=company).annotate(
            warehouse_current_status=Subquery(latest_status_subq, output_field=CharField()),
            warehouse_arrived_at=Subquery(latest_arrived_subq, output_field=DateTimeField()),
            has_warehouse_movement=Exists(
                LoadMovement.objects.filter(
                    load_id=OuterRef("pk"),
                    warehouse=warehouse,
                    status__in=["expected_warehouse", "arrived_warehouse"],
                )
            ),
            total_pieces=Coalesce(
            Sum(
                Cast(
                    NullIf("entry_loads__entry_details__pieces", Value("")),
                    IntegerField(),
                ),
                output_field=IntegerField(),
            ),
            Value(0),
            output_field=IntegerField(),
            ),
            total_weight=Coalesce(
                Sum(
                    Cast(
                        NullIf("entry_loads__entry_details__weight", Value("")),
                        FloatField(),
                    ),
                    output_field=FloatField(),
                ),
                Value(0.0),
                output_field=FloatField(),
            ),
            total_volume=Coalesce(
                Sum(
                    Cast(
                        NullIf("entry_loads__entry_details__volume", Value("")),
                        FloatField(),
                    ),
                    output_field=FloatField(),
                ),
                Value(0.0),
                output_field=FloatField(),
            ),
            total_ldm=Coalesce(
                Sum(
                    Cast(
                        NullIf("entry_loads__entry_details__ldm", Value("")),
                        FloatField(),
                    ),
                    output_field=FloatField(),
                ),
                Value(0.0),
                output_field=FloatField(),
            ),
        ).filter(
            has_warehouse_movement=True
        )

        if location_type == "warehouse":
            qs = qs.filter(warehouse_current_status__in=["expected_warehouse", "arrived_warehouse"])
        elif location_type == "trip":
            qs = qs.filter(location_type="trip")
        elif location_type == "delivered":
            qs = qs.filter(location_type="delivered")
        elif location_type == "all":
            pass

        if q:
            qs = qs.filter(
                Q(sn__icontains=q)
                | Q(customer_ref__icontains=q)
                | Q(load_address__icontains=q)
                | Q(unload_address__icontains=q)
                | Q(bill_to__company_name__icontains=q)
                | Q(trip__rn__icontains=q)
                | Q(trip__trip_number__icontains=q)
                | Q(warehouse__name_warehouse__icontains=q)
                | Q(vehicle_tractor__reg_number__icontains=q)
                | Q(vehicle_trailer__reg_number__icontains=q)
            )

        qs = (qs
              .select_related("bill_to", "trip", "warehouse", "vehicle_tractor",
                "vehicle_trailer"))

        return qs.order_by("-warehouse_arrived_at", "-date_created")


class LoadArriveToWarehouseView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadArriveToWarehouseSerializer

    def post(self, request, load_uf):
        print('2580' ,  request.data)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_company = get_user_company(request.user)
        if not user_company:
            raise ValidationError("User has no company.")

        warehouse_uf = serializer.validated_data["warehouse_uf"]


        with transaction.atomic():
            try:
                load = (
                        Load.objects
                        .select_for_update()
                        .select_related("company")
                        .get(uf=load_uf, company=user_company)
                        )
            except Load.DoesNotExist:
                raise NotFound("Load not found.")

            warehouse = get_object_or_404(
                LoadWarehouse,
                uf=warehouse_uf,
                company=user_company,
            )

            if load.location_type == "delivered":
                raise ValidationError("Delivered loads cannot arrive to warehouse.")

            # optional safety: allow only expected warehouse loads
            latest_expected = (
                LoadMovement.objects.filter(
                    load=load,
                    warehouse=warehouse,
                    status="expected_warehouse",
                )
                .order_by("-date")
                .first()
            )

            if not latest_expected and load.location_type != "warehouse":
                raise ValidationError("Load is not expected in this warehouse.")

            changed_fields = []

            if load.location_type != "warehouse":
                load.location_type = "warehouse"
                changed_fields.append("location_type")

            if load.warehouse_id != warehouse.id:
                load.warehouse = warehouse
                changed_fields.append("warehouse")

            if changed_fields:
                load.save(update_fields=changed_fields)

            # remove stale expected record(s) for this load+warehouse
            LoadMovement.objects.filter(
                load=load,
                warehouse=warehouse,
                status="expected_warehouse",
            ).delete()

            LoadMovement.objects.create(
                load=load,
                trip=load.trip,
                from_location="trip",
                to_location="warehouse",
                warehouse=warehouse,
                status="arrived_warehouse",
            )

        return Response(
            {
                "status": "arrived_to_warehouse",
                "load_uf": load.uf,
                "warehouse": {
                    "uf": warehouse.uf,
                    "name_warehouse": warehouse.name_warehouse,
                },
            },
            status=status.HTTP_200_OK,
        )

###### END LOADS IN THE WAREHOUSE ######
