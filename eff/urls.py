from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from eff.views import CompanyDetail, ContactSuggestionAPIView, TargetGroupDetail, TargetGroupListCreate

urlpatterns = [
    path('companies/me/', CompanyDetail.as_view(), name='company_detail'),

    path('groups/', TargetGroupListCreate.as_view(), name='target_groups'),
    path('groups/<str:uf>/', TargetGroupDetail.as_view(),
         name='target_group_detail'),

    path('contact-suggestion/', ContactSuggestionAPIView.as_view(),
         name='contact-suggestion'),


]

urlpatterns = format_suffix_patterns(urlpatterns)
