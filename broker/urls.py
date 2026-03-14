from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *

urlpatterns = [

    path("broker/points/", PointListCreateView.as_view()),
    path("broker/points/<str:uf>/", PointDetailView.as_view()),
    path("broker/points/<str:uf>/members/", PointMembershipListCreateView.as_view()),
    path("broker/memberships/<str:uf>/", PointMembershipDetailView.as_view()),

    path("broker/jobs/", JobListCreateView.as_view()),
    path("broker/jobs/export/", BrokerJobExportAPIView.as_view()),
    path("broker/jobs/<str:uf>/", JobRetrieveUpdateDestroyView.as_view()),
    
    path("broker/service-types/", ServiceTypeListCreateView.as_view()),
    path("broker/service-types/<str:uf>/", ServiceTypeDetailView.as_view()),
    
    path("broker/customer-prices/", CustomerServicePriceListCreateView.as_view()),    

    path("broker/reports/overview/", BrokerReportsOverviewAPIView.as_view()),
    path("broker/reports/employee-performance/", BrokerEmployeePerformanceAPIView.as_view()),
    path("broker/reports/service-price-trends/", BrokerServicePriceTrendsAPIView.as_view()),

    path("broker/pricing/customers/", BrokerSpecialPricingCustomersListAPIView.as_view()),
    path("broker/partners/<str:partner_uf>/pricing/", BrokerPartnerPricingAPIView.as_view()),
    path("broker/special-pricing/<int:pk>/", BrokerSpecialPricingDeleteAPIView.as_view()),

    ###### STAFF ######
    path("broker/staff/", BrokerStaffListAPIView.as_view()),
    path("broker/staff/<str:uf>/", BrokerStaffDetailsView.as_view()),     
    path("broker/staff/<str:uf>/compensation/", BrokerStaffCompensationUpdateView.as_view()),
    path("broker/commission-types/", BrokerCommissionTypeListView.as_view()),
    path("broker/reports/broker-settlement/", BrokerSettlementReportAPIView.as_view()),
    path("broker/reports/broker-settlement/export/", BrokerSettlementExportAPIView.as_view()),
    path("broker/settlements/", BrokerSettlementCreateAPIView.as_view()),


]

urlpatterns = format_suffix_patterns(urlpatterns)
