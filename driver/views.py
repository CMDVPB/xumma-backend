from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.gis.geos import Point, LineString


from abb.utils import get_user_company
from axx.models import Trip
from driver.serializers import ActiveTripSerializer

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
