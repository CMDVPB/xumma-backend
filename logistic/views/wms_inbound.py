from django.utils import timezone
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from abb.utils import get_user_company
from logistic.models import WHInbound
from logistic.serializers.wms_inbound import WHInboundSerializer



class WHInboundViewSet(ModelViewSet):

    serializer_class = WHInboundSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return (
            WHInbound.objects
            .filter(company=user_company)
            .select_related("owner")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(
            company=user_company,
            created_by=self.request.user
        )

    # ----------------------------
    # RECEIVE INBOUND
    # ----------------------------

    @action(detail=True, methods=["post"])
    def receive(self, request, uf=None):

        inbound = self.get_object()

        if inbound.status == WHInbound.Status.RECEIVED:
            return Response(
                {"detail": "Inbound already received"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        inbound.status = WHInbound.Status.RECEIVED
        inbound.received_at = timezone.now()
        inbound.received_by = request.user
        inbound.save(update_fields=["status", "received_at", "received_by"])

        return Response({"status": "received"})