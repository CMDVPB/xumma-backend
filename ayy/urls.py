from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *

urlpatterns = [
    path('document-types/', DocumentTypeListCreateView.as_view()),
    path('document-types/<str:uf>/',
         DocumentTypeRetrieveUpdateDestroyView.as_view(),
         name='document-type-detail',
         ),

    path("cards/", CompanyCardListCreateView.as_view()),
    path("cards/<str:uf>/", CompanyCardRetrieveUpdateDeleteView.as_view()),
    path("cards/<str:uf>/assign/", CompanyCardAssignView.as_view()),
    path("cards/<str:uf>/unassign/",
         CompanyCardUnassignView.as_view()),


    path("cmrs/available/", CMRAvailableView.as_view(), name="cmr-available"),
    path("cmrs/transfer/", CMRTransferView.as_view(), name="cmr-transfer"),
    path("cmrs/transfers/", CMRTransfersView.as_view(), name="cmr-transfers"),

    path("cmrs/available/load/", CMRAvailableForLoadView.as_view(),
         name="cmr-available-load"),
    path("cmrs/consume/", CMRConsumeView.as_view(), name="cmr-consume"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
