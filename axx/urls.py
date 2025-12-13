from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ContactListCreate, ContactDetail


urlpatterns = [
    path('contacts/', ContactListCreate.as_view(), name='contacts'),
    path('contacts/<str:uf>/', ContactDetail.as_view(), name='contact_detail'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
