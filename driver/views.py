import logging
from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from django.contrib.gis.geos import Point, LineString
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


from abb.policies import ItemCostPolicy, ItemForItemCostPolicy, PolicyFilteredQuerysetMixin, TypeCostPolicy
from abb.utils import get_user_company, hex_uuid
from app.models import TypeCost
from axx.models import Load, LoadEvidence, Trip
from ayy.models import ItemCost, ItemForItemCost
from driver.serializers import (
    ActiveTripSerializer, DriverTripSerializer, DriverTripStopSerializer, DriverVehicleSerializer, ItemCostDriverSerializer, ItemForItemCostDriverSerializer, LoadEvidenceSerializer, TripStopReorderSerializer, TripStopSerializer, TripStopVisibilitySerializer, TypeCostSerializer)
from driver.tasks import broadcast_trip_stop_visibility

from .models import DriverLocation, DriverTrackPoint, TripStop

logger = logging.getLogger(__name__)


class DriverLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if lat is None or lng is None:
            return Response(
                {"detail": "lat and lng required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        speed = request.data.get("speed")
        heading = request.data.get("heading")

        obj, _ = DriverLocation.objects.update_or_create(
            driver=request.user,
            defaults={
                "lat": lat,
                "lng": lng,
                "speed": speed,
                "heading": heading,
            }
        )

        # Store historical point
        last_point = (
            DriverTrackPoint.objects
            .filter(driver=request.user)
            .order_by("-recorded_at")
            .first()
        )

        if not last_point or last_point.recorded_at < now() - timedelta(seconds=5):

            DriverTrackPoint.objects.create(
                driver=request.user,
                point=Point(float(lng), float(lat)),  # ← IMPORTANT ORDER
                speed=speed,
                heading=heading,
            )

        return Response(status=status.HTTP_200_OK)


class DispatcherLocationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DriverLocation.objects.select_related("driver").all()

        data = [
            {
                "driver_id": obj.driver.id,
                "name": obj.driver.get_full_name(),
                "lat": obj.lat,
                "lng": obj.lng,
                "speed": obj.speed,
                "heading": obj.heading,
                "updated_at": obj.updated_at,
            }
            for obj in qs
        ]

        return Response(data)


class ActiveTripsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user)

        trips = (
            Trip.objects
            .filter(company=user_company,
                    date_order__isnull=False,
                    date_end__isnull=True
                    )
            .select_related('vehicle_tractor', 'vehicle_trailer')
            .prefetch_related('drivers')
        )

        serializer = ActiveTripSerializer(trips, many=True)
        return Response(serializer.data)


class DriverLocationAPIView(APIView):
    def get(self, request, driver_uf):
        loc = DriverLocation.objects.filter(driver__uf=driver_uf).first()

        if not loc:
            return Response({"detail": "Not found"}, status=404)

        return Response({
            "lat": loc.lat,
            "lng": loc.lng,
            "speed": loc.speed,
            "heading": loc.heading,
            "updated_at": loc.updated_at,
        })


class DriverRouteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver_uf = request.query_params.get("driverUf")
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")

        if not driver_uf or not date_from or not date_to:
            return Response({"detail": "Missing params"}, status=400)

        qs = DriverTrackPoint.objects.filter(
            driver__uf=driver_uf,
            recorded_at__range=[date_from, date_to]
        ).order_by("recorded_at")

        data = [
            {
                "lat": obj.point.y,
                "lng": obj.point.x,
                "speed": obj.speed,
                "heading": obj.heading,
                "recorded_at": obj.recorded_at,
            }
            for obj in qs
        ]

        return Response(data)


###### START DRIVER LOADING ######
class DriverCurrentTripView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user)

        trip = Trip.objects.filter(
            company=user_company,
            drivers=request.user,
            # status__name="in_progress"  # adjust to your system
        ).first()

        if not trip:
            return Response({"detail": "No active trip"})

        return Response(DriverTripSerializer(trip).data)


class ConfirmLoadingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uf):
        user_company = get_user_company(request.user)

        try:
            load = Load.objects.filter(
                company=user_company).select_related("trip").get(uf=uf)
        except Load.DoesNotExist:
            return Response({"detail": "Load not found"}, status=404)

        trip = load.trip

        if not trip:
            return Response({"detail": "Load not assigned to trip"}, status=400)

        if load.driver_status != "available":
            return Response(
                {"detail": "Load is not available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        order = trip.driver_load_order or []

        print('2282', order)

        if load.uf not in order:
            return Response({"detail": "Load not in trip order"}, status=400)

        idx = order.index(load.uf)

        # 🚨 Prevent skipping
        if idx > 0:
            prev_load = Load.objects.get(uf=order[idx - 1])

            if prev_load.driver_status != "loaded":
                return Response(
                    {"detail": "Previous load not completed"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Mark loaded
        load.driver_status = "loaded"
        load.is_loaded = True
        load.date_loaded = timezone.now()
        load.save()

        # ✅ Unlock next load
        if idx + 1 < len(order):
            next_load = Load.objects.get(uf=order[idx + 1])
            next_load.driver_status = "available"
            next_load.save()

        return Response({"success": True})


class UploadLoadEvidenceView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, uf):

        try:
            load = Load.objects.select_related("trip").get(uf=uf)
        except Load.DoesNotExist:
            return Response({"detail": "Load not found"}, status=404)

        # ✅ Security check (CRITICAL)
        if load.trip and request.user not in load.trip.drivers.all():
            return Response(
                {"detail": "Not your load"},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ Business rule (VERY IMPORTANT)
        if load.driver_status != "loaded":
            return Response(
                {"detail": "Load not loaded yet"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LoadEvidenceSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(load=load)
            return Response(serializer.data)

        return Response(serializer.errors, status=400)


class LoadEvidenceDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, uf):

        user_company = get_user_company(request.user)

        try:
            evidence = (
                LoadEvidence.objects
                .select_related("load__company", "load__trip")
                .get(uf=uf)
            )
        except LoadEvidence.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # HARD MULTI-TENANT SECURITY
        if evidence.load.company != user_company:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # DRIVER OWNERSHIP SECURITY (VERY IMPORTANT)
        if evidence.load.trip and request.user not in evidence.load.trip.drivers.all():
            return Response(status=status.HTTP_403_FORBIDDEN)

        evidence.image.delete(save=False)   # delete file
        evidence.delete()                   # delete DB row

        return Response(status=status.HTTP_204_NO_CONTENT)


class LoadEvidenceProxyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uf):

        try:
            photo = (LoadEvidence.objects
                     .get(uf=uf))
        except LoadEvidence.DoesNotExist:
            raise Http404()

        return FileResponse(
            photo.image.open(),
            content_type="image/jpeg",
        )


class UpdateDriverStatus(APIView):
    def patch(self, request, uf):
        new_status = request.data.get("status")

        print('3570', new_status)

        if not new_status:
            return Response(
                {"detail": "Missing status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        load = get_object_or_404(Load, uf=uf)

        load.driver_status = new_status
        load.save(update_fields=["driver_status"])

        return Response({"success": True})


class DriverCurrentTripView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user)

        trip = (
            Trip.objects
            .filter(
                company=user_company,
                drivers=request.user,
                date_end__isnull=True,
            )
            .select_related("vehicle_tractor", "vehicle_trailer")
            .first()
        )

        print('5550', trip)

        if not trip:
            return Response({"detail": "No active trip"}, status=404)

        # Only stops dispatcher selected
        stops = (
            trip.trip_stops
            .filter(is_visible_to_driver=True)
            .order_by("order", "id")
            .select_related("load", "entry")
        )

        print('5554', stops)

        # next stop = first not completed
        next_stop = stops.filter(is_completed=False).order_by(
            "order", "id").first()

        return Response({
            "uf": trip.uf,
            "rn": trip.rn,
            "date_order": trip.date_order,
            "vehicle_tractor": DriverVehicleSerializer(trip.vehicle_tractor).data if trip.vehicle_tractor else None,
            "vehicle_trailer": DriverVehicleSerializer(trip.vehicle_trailer).data if trip.vehicle_trailer else None,

            "stops_version": trip.stops_version,
            "stops": DriverTripStopSerializer(stops, many=True).data,
            "next_stop": DriverTripStopSerializer(next_stop).data if next_stop else None,

            "departure_inspection_completed": trip.departure_inspection_completed,
        })


class DriverTripStopsSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tripUf):
        user_company = get_user_company(request.user)

        trip = get_object_or_404(
            Trip.objects.filter(company=user_company,
                                uf=tripUf, drivers=request.user),
            uf=tripUf
        )

        client_version = request.query_params.get("version")
        try:
            client_version = int(
                client_version) if client_version is not None else None
        except ValueError:
            return Response({"detail": "Invalid version"}, status=400)

        # If client already up-to-date, return small payload
        if client_version is not None and client_version == trip.stops_version:
            return Response({"stops_version": trip.stops_version, "changed": False})

        stops = (
            trip.trip_stops
            .filter(is_visible_to_driver=True)
            .order_by("order", "id")
            .select_related("load", "entry")
        )
        next_stop = stops.filter(is_completed=False).order_by(
            "order", "id").first()

        return Response({
            "stops_version": trip.stops_version,
            "changed": True,
            "stops": DriverTripStopSerializer(stops, many=True).data,
            "next_stop": DriverTripStopSerializer(next_stop).data if next_stop else None,
        })


class DriverCompleteTripStopView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, stopUf):
        user_company = get_user_company(request.user)

        stop = get_object_or_404(
            TripStop.objects.select_for_update().select_related("trip"),
            uf=stopUf
        )

        trip = stop.trip

        # Multi-tenant + ownership
        if trip.company != user_company or request.user not in trip.drivers.all():
            return Response({"detail": "Forbidden"}, status=403)

        # Optional: do not allow completing a stop dispatcher hid from driver
        if not stop.is_visible_to_driver:
            return Response({"detail": "Stop not assigned to driver"}, status=400)

        if stop.is_completed:
            return Response({"status": "ok", "is_completed": True})

        stop.is_completed = True
        stop.date_completed = timezone.now()
        stop.save(update_fields=["is_completed", "date_completed"])

        # bump version so driver UI refreshes (and dispatcher can see change too if using same list endpoint)
        trip.stops_version += 1
        trip.save(update_fields=["stops_version"])

        # Tie load status updates to stops
        if stop.load and stop.type == "pickup":
            stop.load.driver_status = "loaded"
            stop.load.is_loaded = True
            stop.load.date_loaded = timezone.now()
            stop.load.save(
                update_fields=["driver_status", "is_loaded", "date_loaded"])

        return Response({"status": "ok", "is_completed": True, "stops_version": trip.stops_version})


###### END DRIVER LOADING ######

###### START DRIVER COSTS DURING TRIP ######


class TripCostsDriverView(PolicyFilteredQuerysetMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItemCostDriverSerializer
    parser_classes = (MultiPartParser, FormParser)
    policy_class = ItemCostPolicy

    def get_base_queryset(self):
        user_company = get_user_company(self.request.user)

        trip = get_object_or_404(Trip, uf=self.kwargs["trip_uf"])

        return ItemCost.objects.filter(company=user_company, trip=trip)

    def get_trip(self):
        return get_object_or_404(Trip, uf=self.kwargs["trip_uf"])

    def perform_create(self, serializer):
        trip = self.get_trip()
        user_company = get_user_company(self.request.user)

        if not self.policy_class.can_create(self.request.user, trip):
            raise PermissionDenied("Not allowed")

        serializer.save(
            trip=trip,
            created_by=self.request.user,
            company=user_company
        )


class ItemForItemCostDriverList(PolicyFilteredQuerysetMixin, ListAPIView):
    serializer_class = ItemForItemCostDriverSerializer
    policy_class = ItemForItemCostPolicy

    def get_base_queryset(self):
        return ItemForItemCost.objects.all()


class ItemCostDetailDriverView(PolicyFilteredQuerysetMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItemCostDriverSerializer
    policy_class = ItemCostPolicy
    lookup_field = "uf"

    def get_base_queryset(self):
        user_company = get_user_company(self.request.user)
        return ItemCost.objects.filter(company=user_company)

    def get_object(self):
        obj = super().get_object()

        if not self.policy_class.can_modify(self.request.user, obj):
            raise PermissionDenied("Not allowed")

        return obj


class TypeCostDriverList(PolicyFilteredQuerysetMixin, ListAPIView):
    serializer_class = TypeCostSerializer
    policy_class = TypeCostPolicy

    def get_base_queryset(self):
        return TypeCost.objects.all().order_by("serial_number")

###### EMD DRIVER COSTS DURING TRIP ######


###### START TRIP STOPS ######


def generate_trip_stops(trip):

    loads = trip.trip_loads.all()
    order = 1

    for load in loads:
        for entry in load.entry_loads.all():

            if entry.action == "loading":
                stop_type = "pickup"
            elif entry.action == "unloading":
                stop_type = "delivery"
            else:
                continue

            shipper = entry.shipper

            if not shipper:
                logger.warning(
                    f"Entry {entry.id} has no shipper — skipping TripStop")
                continue

            TripStop.objects.create(
                uf=hex_uuid(),
                company=trip.company,
                trip=trip,
                load=load,
                entry=entry,
                type=stop_type,
                order=order,

                title=shipper.name_site if shipper else "Unknown location",

                lat=shipper.lat if shipper else None,
                lon=shipper.lon if shipper else None,
            )

            order += 1


@api_view(["GET"])
@transaction.atomic
def trip_stops_list(request, tripUf):

    trip = Trip.objects.select_for_update().get(uf=tripUf)

    stops_qs = TripStop.objects.filter(trip=trip)

    if not stops_qs.exists():
        generate_trip_stops(trip)
        stops_qs = TripStop.objects.filter(trip=trip)

    stops_qs = stops_qs.order_by("order")

    return Response(TripStopSerializer(stops_qs, many=True).data)


@api_view(["PATCH"])
@transaction.atomic
def trip_stops_reorder(request, tripUf):

    serializer = TripStopReorderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    ordered_ufs = serializer.validated_data["orderedUfs"]

    stops_qs = list(
        TripStop.objects.select_for_update()
        .filter(trip__uf=tripUf)
    )

    stops_map = {s.uf: s for s in stops_qs}

    if set(ordered_ufs) != set(stops_map.keys()):
        return Response(
            {"detail": "Invalid stops list"},
            status=status.HTTP_400_BAD_REQUEST
        )

    OFFSET = 1000  # must exceed max realistic stops count

    # ✅ Phase 1 — move outside constraint space
    for idx, uf in enumerate(ordered_ufs, start=1):
        stops_map[uf].order = idx + OFFSET

    TripStop.objects.bulk_update(stops_map.values(), ["order"])

    # ✅ Phase 2 — assign final values
    for idx, uf in enumerate(ordered_ufs, start=1):
        stops_map[uf].order = idx

    TripStop.objects.bulk_update(stops_map.values(), ["order"])

    # ✅ Version bump (your logic preserved)
    trip = Trip.objects.select_for_update().get(uf=tripUf)
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    return Response({"status": "ok"})


@api_view(["PATCH"])
@transaction.atomic
def trip_stop_toggle_completed(request, stopUf):

    stop = TripStop.objects.select_for_update().get(uf=stopUf)

    stop.is_completed = not stop.is_completed
    stop.date_completed = timezone.now() if stop.is_completed else None
    stop.save(update_fields=["is_completed", "date_completed"])

    trip = stop.trip
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    return Response({"status": "ok"})


@api_view(["PATCH"])
def trip_stop_visibility(request, stopUf):

    stop = TripStop.objects.get(uf=stopUf)

    serializer = TripStopVisibilitySerializer(
        instance=stop,
        data=request.data,
        partial=True
    )

    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({"status": "ok"})


@api_view(["PATCH"])
@transaction.atomic
def trip_stop_toggle_visibility(request, stopUf):
    stop = get_object_or_404(
        TripStop.objects.select_for_update().select_related("trip"), uf=stopUf)

    # business rule: completed cannot be hidden
    if stop.is_completed and stop.is_visible_to_driver:
        return Response({"detail": "Completed stops cannot be hidden"}, status=400)

    stop.is_visible_to_driver = not stop.is_visible_to_driver
    stop.save(update_fields=["is_visible_to_driver"])

    trip = stop.trip
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    # BROADCAST WS EVENT VIA TASK
    broadcast_trip_stop_visibility.delay(
        trip.company_id,
        stop,
    )

    return Response({"status": "ok", "is_visible_to_driver": stop.is_visible_to_driver, "stops_version": trip.stops_version})

###### END TRIP STOPS ######
