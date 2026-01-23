

from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *


urlpatterns = [
    path("stock/balances/", StockBalanceListView.as_view()),

    path("requests/", PartRequestListCreateView.as_view()),
    path("requests/<int:pk>/", PartRequestDetailView.as_view()),

    path("requests/<int:pk>/reserve/", ReserveRequestView.as_view()),
    path("requests/<int:pk>/issue/", IssueRequestView.as_view()),

]

urlpatterns = format_suffix_patterns(urlpatterns)
