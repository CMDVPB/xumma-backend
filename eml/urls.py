from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from eml.views import BasicEmailOptionalAttachmentsView, EmailTemplateCreateView, EmailTemplateUpdateView, EmailTemplatesListView, MailDetailAPIView, MailLabelV2ListAPIView, MailListAPIView


urlpatterns = [
    ### System email service ###
    path('email-basic/', BasicEmailOptionalAttachmentsView.as_view(),
         name='email_basic_no_attachment'),

    path('email-templates/create/', EmailTemplateCreateView.as_view(),
         name='email_template_create'),
    path('email-templates/', EmailTemplatesListView.as_view(),
         name='email_templates_list'),
    path(
        "email-templates/<str:uf>/", EmailTemplateUpdateView.as_view(), name="email_template_update"),


    path("mail/labels/", MailLabelV2ListAPIView.as_view()),
    path("mail/list/", MailListAPIView.as_view()),
    path("mail/details", MailDetailAPIView.as_view()),

]

urlpatterns = format_suffix_patterns(urlpatterns)
