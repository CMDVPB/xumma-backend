from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from eff.views import CompanyDetail, CompanySettingsView, ContactSuggestionAPIView, DamageReportCreateView, DamageReportDetailView, DamageReportListView, ImageGenerateSignedUrlListView, ImageGenerateZipUrlView, SignedImageView, SignedImageZipView, TargetGroupDetail, TargetGroupListCreate, TypeCostListView

urlpatterns = [
    path('companies/me/', CompanyDetail.as_view(), name='company_detail'),
    path('company-settings/', CompanySettingsView.as_view(),
         name='company_settings'),

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

    #     path("api/image-generate/<str:uf>/", ImageGenerateSignedUrlView.as_view()),
    path("image-generate/", ImageGenerateSignedUrlListView.as_view()),
    path("image-signed/<str:uf>/", SignedImageView.as_view()),


    path("image-zip-generate/", ImageGenerateZipUrlView.as_view()),
    path("image-zip-signed/<str:token>/", SignedImageZipView.as_view()),


    path('type-costs/', TypeCostListView.as_view(), name='type-cost-list'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
