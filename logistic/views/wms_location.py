from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from logistic.models import WHLocation
from logistic.serializers.wms_location import WHLocationSerializer



class WHLocationViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WHLocationSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = WHLocation.objects.filter(
            company=user_company
        )

        is_active = self.request.query_params.get("is_active")

        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        return qs.order_by("code")

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(
            company=user_company
        )