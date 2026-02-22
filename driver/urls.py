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


    path("driver/trips/<str:uf>/status/", UpdateDriverStatus.as_view()),
    path("driver/loads/<str:uf>/confirm-loading/", ConfirmLoadingView.as_view()),
    path("driver/loads/<str:uf>/upload-evidence/",
         UploadLoadEvidenceView.as_view(), name="upload-load-evidence"),
    path("load-evidences/<str:uf>/",
         LoadEvidenceProxyView.as_view(), name="load-evidence-proxy"),
    path("load-evidences/<str:uf>/delete/", LoadEvidenceDeleteView.as_view(),
         name="delete-load-evidence",
         ),

    path("driver/trips/current/", DriverCurrentTripView.as_view()),
    path("driver/trips/<str:tripUf>/stops/sync/",
         DriverTripStopsSyncView.as_view()),
    path("driver/stops/<str:stopUf>/complete/",
         DriverCompleteTripStopView.as_view()),

    ###### START DRIVER COSTS DURING TRIP ######
    path("trips/<str:trip_uf>/costs/", TripCostsDriverView.as_view()),
    path("costs/<str:uf>/", ItemCostDetailDriverView.as_view()),
    path("item-for-cost/", ItemForItemCostDriverList.as_view(), name="item-for-cost"),
    path("typecosts/", TypeCostDriverList.as_view(), name="typecosts"),
    ###### EMD DRIVER COSTS DURING TRIP ######


    ###### START TRIP STOPS MANAGER ######
    path("trips/<str:tripUf>/stops/", trip_stops_list),
    path("trips/<str:tripUf>/stops/reorder/", trip_stops_reorder),
    path("trip-stops/<str:stopUf>/toggle-completed/", trip_stop_toggle_completed),
    path("trip-stops/<str:stopUf>/toggle-visibility/",
         trip_stop_toggle_visibility),
    ###### END TRIP STOPS MANAGER ######
]

urlpatterns = format_suffix_patterns(urlpatterns)
