from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.contrib.gis.geos import Point, LineString
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser


from abb.utils import get_user_company
from axx.models import Load, LoadEvidence, Trip
from driver.serializers import ActiveTripSerializer, DriverTripSerializer, LoadEvidenceSerializer

from .models import DriverLocation, DriverTrackPoint


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


###### END DRIVER LOADING ######
