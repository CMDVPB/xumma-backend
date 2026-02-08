from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from ayy.views import DocumentTypeListCreateView, DocumentTypeRetrieveUpdateDestroyView

urlpatterns = [
    path('document-types/', DocumentTypeListCreateView.as_view()),
    path('document-types/<str:uf>/',
         DocumentTypeRetrieveUpdateDestroyView.as_view(),
         name='document-type-detail',
         ),

]

urlpatterns = format_suffix_patterns(urlpatterns)
