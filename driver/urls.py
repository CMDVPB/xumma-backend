from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [
    path("driver/location/update/", DriverLocationUpdateView.as_view()),
    path('driver/route/', DriverRouteAPIView.as_view(), name='driver-route'),

    path("dispatcher/locations/", DispatcherLocationsView.as_view()),

    path('dispatcher/active-trips/', ActiveTripsAPIView.as_view()),

    path('dispatcher/driver-location/<str:driver_uf>/',
         DriverLocationAPIView.as_view(),  name='driver-location'),


]

urlpatterns = format_suffix_patterns(urlpatterns)
