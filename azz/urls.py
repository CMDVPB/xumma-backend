from django.urls import path
from .views import (
    CostImportCreateView,
    CostImportListView,
    CostImportDetailView,
    FuelPreviewView,
    FuelTankDetailView,
    FuelTankListView,
    ImportSuppliersView,
    RerunCostMatchingView,
    TankRefillCreateView,
    TankRefillDetailView,
    TankRefillListView,
    TruckFuelingCreateView,
    TruckFuelingListView,
)

urlpatterns = [
    path("imports/costs/suppliers/", ImportSuppliersView.as_view()),
    path("imports/costs/", CostImportCreateView.as_view()),
    path("imports/costs/list/", CostImportListView.as_view()),
    path("imports/costs/<str:uf>/", CostImportDetailView.as_view()),
    path("imports/retry-matching/", RerunCostMatchingView.as_view(),
         name="rerun-cost-matching",),

    path("fuel/tanks/", FuelTankListView.as_view()),
    path("fuel/tanks/<str:uf>/", FuelTankDetailView.as_view()),
    path("fuel/preview/", FuelPreviewView.as_view(), name="fuel-preview"),


    path("fuel/refills/", TankRefillListView.as_view()),
    path("fuel/refills/create/", TankRefillCreateView.as_view()),
    path("fuel/refills/<str:uf>/", TankRefillDetailView.as_view()),

    path("fuel/fuelings/", TruckFuelingListView.as_view()),
    path("fuel/fuelings/create/", TruckFuelingCreateView.as_view()),


]
