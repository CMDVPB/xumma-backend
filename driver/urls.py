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

    path("driver/trips/current/", DriverCurrentTripView.as_view()),
    path("driver/loads/<str:uf>/confirm-loading/", ConfirmLoadingView.as_view()),
    path("driver/loads/<str:uf>/upload-evidence/",
         UploadLoadEvidenceView.as_view(), name="upload-load-evidence"),

    path("load-evidences/<str:uf>/",
         LoadEvidenceProxyView.as_view(), name="load-evidence-proxy"),

    path("load-evidences/<str:uf>/delete/", LoadEvidenceDeleteView.as_view(),
         name="delete-load-evidence",
         )
]

urlpatterns = format_suffix_patterns(urlpatterns)
