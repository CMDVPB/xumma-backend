from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from auu.models import PaymentMethod
from auu.serializers import PaymentMethodListSerializer


class PaymentMethodListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentMethodListSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = (PaymentMethod.objects
              .filter(
                  is_active=True
              )
              .filter(
                  Q(is_system=True) |
                  Q(company=user_company)
              ))

        return qs
