from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from dtt.views import AuthorizationStockBatchDetailsView, AuthorizationStockBatchListCreateView, BankAccountDetailView, BankAccountListCreateView, \
    CMRStockBatchDetailsView, CMRStockBatchListCreateView, CTIRStockBatchDetailsView, CTIRStockBatchListCreateView, ColliTypeListView, ContactSiteCreateView, ContactSiteDetailView, \
    ContactSiteListView, ItemForItemCostDetailView, ItemForItemCostListCreateView, ItemForItemInvDetailView, ItemForItemInvListCreateView, NoteDetailView, NoteListCreateView, PaymentTermListCreateView, PaymentTermsDetailView, TermDetailView, TermListCreateView, UserSettingsView, \
    get_post_delete_user_smtp_settings, test_smtp_connection_view

urlpatterns = [

    path('colli-types/', ColliTypeListView.as_view(),
         name='colli_types'),

    path('bank-accounts/', BankAccountListCreateView.as_view(), name='bank_accounts'),
    path('bank-accounts/<str:uf>/', BankAccountDetailView.as_view(),
         name='bank_account_detail'),

    path('items-for-item-inv/', ItemForItemInvListCreateView.as_view(),
         name='items_for_item_inv'),
    path('items-for-item-inv/<str:uf>/', ItemForItemInvDetailView.as_view(),
         name='items_for_item_inv_detail'),

    path('items-for-item-cost/', ItemForItemCostListCreateView.as_view(),
         name='items_for_item_cost'),
    path('items-for-item-cost/<str:uf>/', ItemForItemCostDetailView.as_view(),
         name='items_for_item_cost_detail'),

    path('notes/', NoteListCreateView.as_view(), name='notes'),
    path('notes/<str:uf>/', NoteDetailView.as_view(), name='note_detail'),

    path('terms/', TermListCreateView.as_view(), name='terms'),
    path('terms/<str:uf>/', TermDetailView.as_view(), name='term_detail'),

    path('terms-of-payment/', PaymentTermListCreateView.as_view(),
         name='payment_terms'),
    path('terms-of-payment/<str:uf>/',
         PaymentTermsDetailView.as_view(), name='payment_term_detail'),

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

    path('contact-sites/', ContactSiteListView.as_view(), name='contact_sites'),
    path('contact-sites/create/', ContactSiteCreateView.as_view(),
         name='contact_site_create'),
    path('contact-sites/<str:uf>/', ContactSiteDetailView.as_view(),
         name='contact_site_detail'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
