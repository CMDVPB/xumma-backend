from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from logistic.models import WHProduct
from logistic.serializers.wms_product import WHProductDetailsSerializer, WHProductSerializer



class WHProductViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]    
    lookup_field = "uf"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WHProductDetailsSerializer
        return WHProductSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = (
            WHProduct.objects
            .filter(company=user_company)
            .select_related("owner")
        )

        owner = self.request.query_params.get("owner")

        is_active = self.request.query_params.get("is_active")

        if owner:
            qs = qs.filter(owner__uf=owner)

        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)

        serializer.save(company=user_company)