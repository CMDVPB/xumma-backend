from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from dff.views.views_user import UserCreate, UserDetailSelf, UserManagerCreate

urlpatterns = [


    path('users/create-manager/', UserManagerCreate.as_view(),
         name='user_create_manager'),
    path('users-create/', UserCreate.as_view(), name='user_create'),
    path('users/me/', UserDetailSelf.as_view(), name='user_detail'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
