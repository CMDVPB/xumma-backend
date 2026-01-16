from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from eff.views import CompanyDetail, ContactSuggestionAPIView, DamageReportCreateView, DamageReportDetailView, DamageReportListView, ImageGenerateSignedUrlView, SignedImageView, TargetGroupDetail, TargetGroupListCreate

urlpatterns = [
    path('companies/me/', CompanyDetail.as_view(), name='company_detail'),

    path('groups/', TargetGroupListCreate.as_view(), name='target_groups'),
    path('groups/<str:uf>/', TargetGroupDetail.as_view(),
         name='target_group_detail'),

    path('contact-suggestion/', ContactSuggestionAPIView.as_view(),
         name='contact-suggestion'),

    path('damage-reports/', DamageReportListView.as_view(),
         name='damage_reports'),
    path('damage-reports/create/', DamageReportCreateView.as_view(),
         name='damage_report_create'),

    path('damage-reports/<str:uf>/', DamageReportDetailView.as_view(),
         name='damage_report_detail'),

    path("api/image-generate/<str:uf>/", ImageGenerateSignedUrlView.as_view()),
    path("api/image-signed/<uuid:token>/", SignedImageView.as_view()),

]

urlpatterns = format_suffix_patterns(urlpatterns)
