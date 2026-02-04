from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from att.views import BodyTypeListView, CategoryGeneralListView, ContactStatusListAPIView, ContactStatusUpdateAPIView, EmissionClassListView, IncotermListView, \
    ModeTypeListView, RouteSheetStockBatchDetailsView, RouteSheetStockBatchListCreateView, StatusTypeListView, TypeGeneralListView, VehicleBrandListView, VehicleCreateView, \
    VehicleDetailView, VehicleDocumentCreateView, VehicleDocumentDeleteView, VehicleDocumentListView, VehicleDocumentUpdateView, VehicleListView

urlpatterns = [

    ### Unauthenticated ###
    path('incoterms/', IncotermListView.as_view(), name='incoterms'),
    path('modes/', ModeTypeListView.as_view(), name='mode-types'),
    path('body-types/', BodyTypeListView.as_view(), name='body-types'),
    path('status-types/', StatusTypeListView.as_view(), name='status-types'),

    ### Authenticated ###
    path('types/', TypeGeneralListView.as_view(), name='types'),
    path('categories/', CategoryGeneralListView.as_view(), name='categories'),

    path('emission-classes/', EmissionClassListView.as_view(),
         name='emission-classes'),
    path('vehicle-brands/', VehicleBrandListView.as_view(), name='vehicle-brands'),

    path('vehicles/create/', VehicleCreateView.as_view(),
         name='vehicle-create'),
    path('vehicles/', VehicleListView.as_view(), name='vehicle-list'),
    path('vehicles/<str:uf>/', VehicleDetailView.as_view(),
         name='vehicle-details'),

    path('route-sheet-stock/', RouteSheetStockBatchListCreateView.as_view(),
         name='route-sheets_list_create'),
    path('route-sheet-stock/<str:uf>/', RouteSheetStockBatchDetailsView.as_view(),
         name='route-sheets_details'),

    path('vehicle-documents/', VehicleDocumentCreateView.as_view(),
         name='vehicle-document-create'),
    path('vehicle-documents/<int:pk>/',
         VehicleDocumentUpdateView.as_view(), name='vehicle-document-update'),
    path('vehicle-documents/<int:pk>/delete/',
         VehicleDocumentDeleteView.as_view(), name='vehicle-document-delete'),
    path('vehicle-documents/list/', VehicleDocumentListView.as_view(),
         name='vehicle-document-list'),


    path("contact-statuses/", ContactStatusListAPIView.as_view(),
         name="contact-status-list"
         ),
    path("contacts/<str:uf>/status/", ContactStatusUpdateAPIView.as_view(),
         name="contact-status-update"),
]

urlpatterns = format_suffix_patterns(urlpatterns)
