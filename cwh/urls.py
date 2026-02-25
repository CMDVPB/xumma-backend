from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [

    path("load-warehouses/", LoadWarehouseListView.as_view(),
         name="load-warehouse-list"),
    path("load-warehouses/create/", LoadWarehouseCreateView.as_view(),
         name="load-warehouse-create"),
    path("load-warehouses/<str:warehouseUf>/",
         LoadWarehouseDetailView.as_view(), name="load-warehouse-detail"),
    path("load-warehouses/<str:warehouseUf>/loads/",
         WarehouseLoadListView.as_view(), name="load-warehouse-loads"),

    path("loads/<str:load_uf>/unload-to-warehouse/", LoadUnloadToWarehouseView.as_view(),
         name="load-unload-to-warehouse"),
    path("loads/bulk-unload-to-warehouse/", BulkUnloadLoadsToWarehouseView.as_view(),
         name="loads-bulk-unload-to-warehouse"),
    path("loads/<str:load_uf>/reload-to-trip/", LoadReloadToTripView.as_view(),
         name="load-reload-to-trip"),




]

urlpatterns = format_suffix_patterns(urlpatterns)
