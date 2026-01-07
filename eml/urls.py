from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from eml.views import BasicEmailNoAttachmentView, EmailTemplateCreateView, EmailTemplateUpdateView, EmailTemplatesListView


urlpatterns = [
    ### System email service ###
    path('email-basic/', BasicEmailNoAttachmentView.as_view(),
         name='email_basic_no_attachment'),

    path('email-templates/create/', EmailTemplateCreateView.as_view(),
         name='email_template_create'),
    path('email-templates/', EmailTemplatesListView.as_view(),
         name='email_templates_list'),
    path(
        "email-templates/<str:uf>/", EmailTemplateUpdateView.as_view(), name="email_template_update",)


]

urlpatterns = format_suffix_patterns(urlpatterns)
