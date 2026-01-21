from django.urls import path
from .views import (
    CostImportCreateView,
    CostImportListView,
    CostImportDetailView,
    ImportSuppliersView,
    RerunCostMatchingView,
)

urlpatterns = [
    path("imports/costs/suppliers/", ImportSuppliersView.as_view()),
    path("imports/costs/", CostImportCreateView.as_view()),
    path("imports/costs/list/", CostImportListView.as_view()),
    path("imports/costs/<str:uf>/", CostImportDetailView.as_view()),

    path("imports/retry-matching/", RerunCostMatchingView.as_view(),
         name="rerun-cost-matching",),
]
