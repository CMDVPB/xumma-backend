from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from dff.views.views_inv import InvCreateView, InvDetailView, InvListView
from dff.views.views_load import CancelInvoiceView, IssueInvoiceView, LoadCreateView, LoadDetailView, LoadListForTripView, LoadListView
from dff.views.views_quote import QuoteCreateView, QuoteDetailView, QuoteListView
from dff.views.views_trip import TripCreateView, TripDetailView, TripListView, get_trips_trucks_view
from dff.views.views_user import CompanyUsersView, UserAvatarView, UserCreate, UserDetailSelfOrByManagerView, UserDetailSelfView, UserCompleteView, UserManagerCreate

urlpatterns = [

    path('users/create-manager/', UserManagerCreate.as_view(),
         name='user_create_manager'),
    path('users-create/', UserCreate.as_view(), name='user_create'),
    path('users/me/', UserDetailSelfView.as_view(), name='user_detail'),
    path('users/<str:uf>/', UserDetailSelfOrByManagerView.as_view(),
         name='user_details'),
    path('employees/<str:uf>/', UserCompleteView.as_view(),
         name='user_complete_details'),
    path('users-avatar/<str:uf>/', UserAvatarView.as_view(), name='users-avatar'),
    path('users/company/', CompanyUsersView.as_view(), name='company-users'),

    path('loads/', LoadListView.as_view(), name='loads'),
    path('loads/create/', LoadCreateView.as_view(), name='load_create'),
    path('loads/<str:uf>/', LoadDetailView.as_view(), name='load_detail'),
    path('trip-loads/', LoadListForTripView.as_view(),
         name='load_list_for_trip'),
    path('loads/<str:load_uf>/issue-invoice/',
         IssueInvoiceView.as_view(), name='issue-load-invoice'),
    path('loads/<str:load_uf>/cancel-invoice/',
         CancelInvoiceView.as_view(), name='cancel-load-invoice'),

    path('trips/', TripListView.as_view(), name='trips'),
    path('trips/create/', TripCreateView.as_view(), name='trip_create'),
    path('trips/<str:uf>/', TripDetailView.as_view(), name='trip_detail'),
    path('trips-trucks/', get_trips_trucks_view, name='trips_trucks'),


    path('invs/', InvListView.as_view(), name='invs'),
    path('invs/create/', InvCreateView.as_view(), name='inv_create'),
    path('invs/<str:uf>/', InvDetailView.as_view(), name='inv_detail'),

    path('quotes/', QuoteListView.as_view(), name='quotes'),
    path('quotes/create/', QuoteCreateView.as_view(), name='quote_create'),
    path('quotes/<str:uf>/', QuoteDetailView.as_view(), name='quote_detail'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
