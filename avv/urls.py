

from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *


urlpatterns = [
    path('parts/', PartListView.as_view()),
    path("parts/create/", PartCreateView.as_view()),
    path("parts/<int:pk>/", PartDetailView.as_view()),

    path("stock/", StockListView.as_view()),
    path("stock/balances/", StockBalanceListView.as_view()),
    path("stock/receive/", StockReceiveView.as_view(), name="stock-receive"),

    path("requests/", PartRequestListCreateView.as_view()),
    path("requests/<int:pk>/", PartRequestDetailView.as_view()),
    path("requests/<int:pk>/reserve/", ReserveRequestView.as_view()),
    path("requests/<int:pk>/issue/", IssueRequestView.as_view()),

    path("warehouses/", WarehouseListView.as_view(), name="warehouse-list"),

    path("locations/", LocationListView.as_view(), name="location-list"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
