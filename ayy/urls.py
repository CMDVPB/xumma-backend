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
    path("card-providers/", CardProviderListAPIView.as_view()),
    path("card-providers/create/", CardProviderCreateAPIView.as_view()),
    path("card-providers/<str:uf>/", CardProviderUpdateAPIView.as_view()),
    path("card-providers/<str:uf>/delete/",
         CardProviderDeleteAPIView.as_view()),
    path("cards/<str:card_uf>/periods/",
         CardPeriodsView.as_view(),
         name="card-periods",
         ),

    path("cmrs/available/", CMRAvailableView.as_view(), name="cmr-available"),
    path("cmrs/transfer/", CMRTransferView.as_view(), name="cmr-transfer"),
    path("cmrs/transfers/", CMRTransfersView.as_view(), name="cmr-transfers"),

    path("cmrs/available/load/", CMRAvailableForLoadView.as_view(),
         name="cmr-available-load"),
    path("cmrs/consume/", CMRConsumeView.as_view(), name="cmr-consume"),
    path('cmrs/unconsume/<str:load_uf>/', CmrUnconsumeView.as_view()),

]

urlpatterns = format_suffix_patterns(urlpatterns)
