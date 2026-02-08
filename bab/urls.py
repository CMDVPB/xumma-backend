from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [

    path('document-templates/default/', DefaultDocumentTemplateView.as_view(),
         name='document-template-default'),

    path("draft/preview/<str:load_uf>/", DraftInvoicePreviewView.as_view(),
         name="draft-invoice-preview",
         ),

    path("draft/html-preview/", HtmlToPdfPreviewView.as_view(),
         name="html-to-pdf-preview"),


    path("invoice/pdf/", InvoicePdfView.as_view()),


]

urlpatterns = format_suffix_patterns(urlpatterns)
