from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ContactListCreate, ContactDetail, ContractListView


urlpatterns = [
    path('contacts/', ContactListCreate.as_view(), name='contacts'),
    path('contacts/<str:uf>/', ContactDetail.as_view(), name='contact_detail'),

    path('contracts/', ContractListView.as_view(), name='contracts'),
    # path('contracts/<str:uf>/', ContractDetail.as_view(), name='contract_detail'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
