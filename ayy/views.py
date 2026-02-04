from django.db.models import QuerySet, Q
from rest_framework import generics, permissions

from abb.utils import get_user_company
from .models import DocumentType
from .serializers import (
    DocumentTypeSerializer,
    DocumentTypeCreateSerializer
)


class DocumentTypeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)
        qs = DocumentType.objects.filter(is_active=True)

        # system + company-specific
        qs = qs.filter(
            Q(is_system=True) |
            Q(company=user_company)
        )

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)

        return qs.order_by('order', 'name')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DocumentTypeCreateSerializer
        return DocumentTypeSerializer
