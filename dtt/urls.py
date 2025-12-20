from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from dtt.views import AuthorizationStockBatchDetailsView, AuthorizationStockBatchListCreateView, CMRStockBatchDetailsView, CMRStockBatchListCreateView, CTIRStockBatchDetailsView, CTIRStockBatchListCreateView, UserSettingsView, get_post_delete_user_smtp_settings, test_smtp_connection_view

urlpatterns = [

    path('smtp-test/', test_smtp_connection_view, name='smtp_test'),
    path('smtp-settings/', get_post_delete_user_smtp_settings, name='smtp_settings'),
    path('user-settings/', UserSettingsView.as_view(), name='user_settings'),

    path('cmrs/', CMRStockBatchListCreateView.as_view(), name='cmrs_list_create'),
    path('cmrs/<str:uf>/', CMRStockBatchDetailsView.as_view(), name='cmrs_details'),

    path('authorizations/', AuthorizationStockBatchListCreateView.as_view(),
         name='authorizations_list_create'),
    path('authorizations/<str:uf>/', AuthorizationStockBatchDetailsView.as_view(),
         name='authorizations_details'),

    path('ctirs/', CTIRStockBatchListCreateView.as_view(), name='ctir_list_create'),
    path('ctirs/<str:uf>/', CTIRStockBatchDetailsView.as_view(), name='ctir_details'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
