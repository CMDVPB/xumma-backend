

from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *


urlpatterns = [
    path("uoms/", UnitOfMeasureListView.as_view(), name="uom-list"),

    path("warehouses/", WarehouseListView.as_view(), name="warehouse-list"),

    path("locations/", LocationListView.as_view(), name="location-list"),
    path("locations/by-part/", LocationsByPartView.as_view(),
         name="locations-by-part"),
    path("locations/by-part/<int:part_id>/",
         LocationsByPartView.as_view(), name="locations-by-part"),

    path('parts/', PartListView.as_view()),
    path("parts/create/", PartCreateView.as_view()),
    path("parts/<int:pk>/", PartDetailView.as_view()),

    path("requests/", PartRequestListCreateView.as_view()),
    path("requests/<int:pk>/", PartRequestDetailView.as_view()),
    path("requests/<int:pk>/reserve/", ReserveRequestView.as_view()),
    path("requests/<int:pk>/issue/", IssueRequestView.as_view()),

    path("issues/", IssueDocumentListView.as_view()),
    path("issues/<int:pk>/", IssueDocumentDetailView.as_view()),
    path("issues/<int:pk>/confirm/", IssueDocumentConfirmView.as_view()),

    path("work-orders/", WorkOrderListView.as_view()),
    path("work-orders/create/", WorkOrderCreateView.as_view()),
    path("work-orders/<int:pk>/", WorkOrderDetailView.as_view()),
    path("work-orders/<int:pk>/start/",
         WorkOrderStartView.as_view(), name="work-order-start"),
    path("work-orders/<int:pk>/issue/", WorkOrderIssueView.as_view()),
    path("work-orders/<int:pk>/issues/", WorkOrderIssueListView.as_view()),
    path("work-orders/<int:pk>/complete/",
         WorkOrderCompleteView.as_view(), name="workorder-complete"),

    path("stock/", StockListView.as_view()),
    path("stock/balances/", StockBalanceListView.as_view()),
    path("stock/receive/", StockReceiveView.as_view(), name="stock-receive"),
    path("stock/transfer/", StockTransferView.as_view(), name="stock-transfer"),
    path("stock/movements/", StockMovementListView.as_view(), name="stock-movements"),


]
