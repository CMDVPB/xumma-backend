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
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes


from abb.permissions import NotDriverPermission
from abb.policies import ItemCostPolicy, ItemForItemCostPolicy, PolicyFilteredQuerysetMixin, TypeCostPolicy
from abb.utils import get_user_company, hex_uuid
from app.models import TypeCost
from axx.models import Load, LoadEvidence, Trip
from ayy.models import ItemCost, ItemForItemCost
from driver.serializers import (
    ActiveTripSerializer, DriverLoadCacheSerializer, DriverTripSerializer, DriverTripStopSerializer, DriverVehicleSerializer, ItemCostDriverSerializer, ItemForItemCostDriverSerializer, LoadEvidenceSerializer, TripStopMessageSerializer, TripStopReorderSerializer, TripStopSerializer, TripStopVisibilitySerializer, TypeCostSerializer)
from driver.tasks import broadcast_trip_stop_messages_read, broadcast_trip_stop_reorder, broadcast_trip_stop_visibility

from .models import DriverLocation, DriverTrackPoint, TripStop, TripStopMessage

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


###### START DRIVER CONFIRMTIONS ######
class DriverConfirmArrivalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uf):
        company = get_user_company(request.user)

        try:
            stop = TripStop.objects.get(uf=uf, company=company)
        except TripStop.DoesNotExist:
            return Response({"detail": "Stop not found"}, status=404)

        if stop.status != "pending":
            return Response(
                {"detail": f"Cannot confirm arrival from state '{stop.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stop.status = "arrived"
        stop.save()

        return Response({"success": True})


class DriverStartStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uf):
        company = get_user_company(request.user)

        try:
            stop = TripStop.objects.get(uf=uf, company=company)
        except TripStop.DoesNotExist:
            return Response({"detail": "Stop not found"}, status=404)

        if stop.status != "arrived":
            return Response(
                {"detail": f"Stop must be 'arrived' (current: '{stop.status}')"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stop.status = "in_progress"
        stop.save()

        return Response({"success": True})


class DriverCompleteStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uf):
        company = get_user_company(request.user)

        try:
            stop = TripStop.objects.get(uf=uf, company=company)
        except TripStop.DoesNotExist:
            return Response({"detail": "Stop not found"}, status=404)

        if stop.status != "in_progress":
            return Response(
                {"detail": f"Stop must be 'in_progress' (current: '{stop.status}')"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stop.status = "completed"
        stop.save()

        return Response({"success": True})


class DriverSkipStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uf):
        company = get_user_company(request.user)

        try:
            stop = TripStop.objects.get(uf=uf, company=company)
        except TripStop.DoesNotExist:
            return Response({"detail": "Stop not found"}, status=404)

        if stop.status not in ["pending", "arrived"]:
            return Response(
                {"detail": f"Cannot skip stop from state '{stop.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stop.status = "skipped"
        stop.save()

        return Response({"success": True})


###### END DRIVER CONFIRMTIONS ######

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
            .select_related("load", "entry")
            .annotate(
                unread_count=Count(
                    "trip_stop_messages",
                    filter=Q(trip_stop_messages__is_read_by_driver=False)
                    & ~Q(trip_stop_messages__sender__groups__name="level_driver"),
                    distinct=True,
                ),

            )
            .order_by("order", "id")
        )

        # print('5554', stops)

        # next stop = first not completed
        next_stop = stops.exclude(status__in=["completed", "skipped"]).first()

        loads = (
            Load.objects
            .filter(trip=trip)
            .prefetch_related("load_evidences")
        )

        loads_cache = {
            str(load.sn): DriverLoadCacheSerializer(load).data
            for load in loads
        }

        return Response({
            "uf": trip.uf,
            "rn": trip.rn,
            "date_order": trip.date_order,
            "vehicle_tractor": DriverVehicleSerializer(trip.vehicle_tractor).data if trip.vehicle_tractor else None,
            "vehicle_trailer": DriverVehicleSerializer(trip.vehicle_trailer).data if trip.vehicle_trailer else None,

            "stops_version": trip.stops_version,
            "stops": DriverTripStopSerializer(stops, many=True).data,
            "next_stop": DriverTripStopSerializer(next_stop, context={}).data if next_stop else None,

            "loads_cache": loads_cache,

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
        next_stop = stops.filter(~Q(status='completed')).order_by(
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
    def post(self, request, stopUf):
        user_company = get_user_company(request.user)

        # lock ONLY TripStop row (no nullable joins)
        stop = get_object_or_404(
            TripStop.objects.select_for_update().select_related("trip"),
            uf=stopUf,
        )
        trip = stop.trip

        # Multi-tenant + ownership
        if trip.company_id != user_company.id or not trip.drivers.filter(id=request.user.id).exists():
            return Response({"detail": "Forbidden"}, status=403)

        if not stop.is_visible_to_driver:
            return Response({"detail": "Stop not assigned to driver"}, status=400)

        if stop.status == "completed":
            return Response({"status": "ok", "stop_status": stop.status, "stops_version": trip.stops_version})

        if stop.status == "skipped":
            return Response({"detail": "Cannot complete skipped stop"}, status=400)

        if stop.status != "in_progress":
            return Response({"detail": f"Invalid transition from {stop.status}"}, status=400)

        # complete stop
        stop.status = "completed"
        stop.date_completed = timezone.now()
        stop.save(update_fields=["status", "date_completed"])

        # bump version
        trip.stops_version += 1
        trip.save(update_fields=["stops_version"])

        # optional load side-effects (fetch separately; lock if needed)
        if stop.load_id:
            load = Load.objects.select_for_update().get(id=stop.load_id)

            if stop.type == "pickup":
                load.is_loaded = True
                load.date_loaded = timezone.now()
                load.save(update_fields=["is_loaded", "date_loaded"])

            elif stop.type == "delivery":
                load.is_unloaded = True
                load.date_unloaded = timezone.now()
                load.save(update_fields=["is_unloaded", "date_unloaded"])

        return Response({
            "status": "ok",
            "stop_status": stop.status,
            "stops_version": trip.stops_version
        })
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


def _generate_trip_stops(trip):

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
@permission_classes([IsAuthenticated, NotDriverPermission])
@transaction.atomic
def trip_stops_list(request, tripUf):

    trip = Trip.objects.select_for_update().get(uf=tripUf)

    stops_qs = TripStop.objects.filter(trip=trip)

    if not stops_qs.exists():
        _generate_trip_stops(trip)
        stops_qs = TripStop.objects.filter(trip=trip)

    stops_qs = stops_qs.order_by("order")

    return Response(TripStopSerializer(stops_qs, many=True, context={"request": request}).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, NotDriverPermission])
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

    # Version bump (your logic preserved)
    trip = Trip.objects.select_for_update().get(uf=tripUf)
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    # Broadcast AFTER commit-safe state
    transaction.on_commit(
        lambda: broadcast_trip_stop_reorder.delay(trip.uf)
    )

    return Response({"status": "ok"})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, NotDriverPermission])
@transaction.atomic
def trip_stop_complete(request, stopUf):

    user = request.user

    if user.groups.filter(name="level_driver").exists():
        return Response(
            {"detail": "Drivers cannot use this endpoint"},
            status=status.HTTP_403_FORBIDDEN
        )

    stop = get_object_or_404(
        TripStop.objects.select_for_update(),
        uf=stopUf
    )

    if stop.status == "completed":
        stop.status = "pending"
        stop.date_completed = None
        stop.save(update_fields=["status", "date_completed"])

        trip = stop.trip
        trip.stops_version += 1
        trip.save(update_fields=["stops_version"])

        return Response({"status": "ok"})

    if stop.status == "skipped":
        return Response(
            {"detail": "Cannot complete skipped stop"},
            status=400
        )

    stop.status = "completed"
    stop.date_completed = timezone.now()
    stop.save(update_fields=["status", "date_completed"])

    trip = stop.trip
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    return Response({"status": "ok", "stops_version": trip.stops_version})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, NotDriverPermission])
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
@permission_classes([IsAuthenticated, NotDriverPermission])
@transaction.atomic
def trip_stop_toggle_visibility_by_dispatcher(request, stopUf):

    stop = get_object_or_404(
        TripStop.objects.select_for_update().select_related("trip"),
        uf=stopUf
    )

    if stop.status in ["arrived", "in_progress"]:
        stop.status = "pending"
        stop.save(update_fields=["status", "date_completed"])

    if stop.status == "completed" and stop.is_visible_to_driver:
        return Response(
            {"detail": "Completed stops cannot be hidden"},
            status=400
        )

    stop.is_visible_to_driver = not stop.is_visible_to_driver
    stop.save(update_fields=["is_visible_to_driver"])

    trip = stop.trip
    trip.stops_version += 1
    trip.save(update_fields=["stops_version"])

    broadcast_trip_stop_visibility.delay(
        trip.company_id,
        stop.uf,
    )

    return Response({
        "status": "ok",
        "is_visible_to_driver": stop.is_visible_to_driver,
        "stops_version": trip.stops_version
    })

###### END TRIP STOPS ######

###### START TRIP STOP MESSAGING ######


class TripStopMessageListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripStopMessageSerializer

    def get_trip_stop(self):
        uf = self.kwargs["uf"]

        try:
            stop = TripStop.objects.select_related(
                "trip", "company").get(uf=uf)
        except TripStop.DoesNotExist:
            raise NotFound("Trip stop not found")

        user_company = get_user_company(self.request.user)

        if stop.company_id != user_company.id:
            raise PermissionDenied("Invalid company")

        return stop

    def get_queryset(self):
        stop = self.get_trip_stop()

        return TripStopMessage.objects.filter(
            trip_stop=stop
        ).select_related("sender")

    def perform_create(self, serializer):
        stop = self.get_trip_stop()

        serializer.save(
            company=stop.company,
            trip_stop=stop,
            sender=self.request.user,
        )


class TripStopMessageMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_trip_stop(self, uf):
        try:
            stop = TripStop.objects.select_related("company").get(uf=uf)
        except TripStop.DoesNotExist:
            raise NotFound("Trip stop not found")

        user_company = get_user_company(self.request.user)

        if stop.company_id != user_company.id:
            raise PermissionDenied("Invalid company")

        return stop

    def post(self, request, uf):
        stop = self.get_trip_stop(uf)

        user = request.user
        user_company = get_user_company(user)

        # Decide which flag to update
        if self.request.user.groups.filter(name='level_driver').exists():
            updated = TripStopMessage.objects.filter(
                trip_stop=stop,
                is_read_by_driver=False,
            ).update(is_read_by_driver=True)

        else:  # other than driver
            updated = TripStopMessage.objects.filter(
                trip_stop=stop,
                is_read_by_dispatcher=False,
            ).update(is_read_by_dispatcher=True)

        broadcast_trip_stop_messages_read.delay(user_company.id, stop.uf)

        return Response({
            "status": "ok",
            "updated": updated,
        })

###### END TRIP STOP MESSAGING ######
