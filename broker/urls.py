from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *

urlpatterns = [

    path("broker/points/", PointListCreateView.as_view()),
    path("broker/points/<str:uf>/", PointDetailView.as_view()),
    path("broker/points/<str:uf>/members/", PointMembershipListCreateView.as_view()),
    path("broker/memberships/<str:uf>/", PointMembershipDetailView.as_view()),

    path("broker/jobs/", JobListCreateView.as_view()),
    path("broker/jobs/<str:uf>/", JobRetrieveUpdateDestroyView.as_view()),
    
    path("broker/service-types/", ServiceTypeListCreateView.as_view()),
    path("broker/service-types/<str:uf>/", ServiceTypeDetailView.as_view()),
    
    path("broker/customer-prices/", CustomerServicePriceListCreateView.as_view()),    

]

urlpatterns = format_suffix_patterns(urlpatterns)
