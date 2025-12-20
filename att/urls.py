from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from att.views import BodyTypeListView, CategoryGeneralListView, EmissionClassListView, IncotermListView, \
    ModeTypeListView, StatusTypeListView, TypeGeneralListView, VehicleBrandListView, VehicleCompanyCreateView, \
    VehicleCompanyDetailView, VehicleCompanyListView

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

    path('vehicles/create/', VehicleCompanyCreateView.as_view(),
         name='vehicle-create'),
    path('vehicles/', VehicleCompanyListView.as_view(), name='vehicle-list'),
    path('vehicles/<str:uf>/', VehicleCompanyDetailView.as_view(),
         name='vehicle-details'),


]

urlpatterns = format_suffix_patterns(urlpatterns)
