from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from logistic.models import WHOutbound
from logistic.serializers.wms_outbound import WHOutboundSerializer




class WHOutboundViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WHOutboundSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return WHOutbound.objects.filter(
            company=user_company
        ).select_related("owner")