from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ContactListCreate, ContactDetail, ContractListView, GenerateLoadDocumentView, LoadDocumentProxyView, LoadDocumentsView, LoadInvListView, LoadMergedPdfView, TripAdvancePaymentChangeStatusView, TripAdvancePaymentCreateView, TripAdvancePaymentDeleteView, TripAdvancePaymentListView


urlpatterns = [
    path('contacts/', ContactListCreate.as_view(), name='contacts'),
    path('contacts/<str:uf>/', ContactDetail.as_view(), name='contact_detail'),

    path('contracts/', ContractListView.as_view(), name='contracts'),
    # path('contracts/<str:uf>/', ContractDetail.as_view(), name='contract_detail'),

    path('trips/<str:trip_uf>/advance-payments/', TripAdvancePaymentListView.as_view()
         ),
    path('advance-payments/', TripAdvancePaymentCreateView.as_view()
         ),
    path('advance-payments/<str:uf>/change-status/', TripAdvancePaymentChangeStatusView.as_view()
         ),
    path('advance-payments/<str:uf>/', TripAdvancePaymentDeleteView.as_view(),
         name='advance-payment-delete'
         ),


    path("loads/<str:load_uf>/documents/<str:doc_type>/generate/",
         GenerateLoadDocumentView.as_view()),
    path("loads/<str:load_uf>/documents/", LoadDocumentsView.as_view(),
         name="load-documents",
         ),
    path("load-documents/<str:uf>/", LoadDocumentProxyView.as_view(),
         name="load-document-proxy",
         ),
    path(
        "loads/<str:load_uf>/documents/merged/",
        LoadMergedPdfView.as_view(),
        name="load-merged-pdf",
    ),

    path("invoices/", LoadInvListView.as_view(), name="loadinv-list"),


]

urlpatterns = format_suffix_patterns(urlpatterns)
