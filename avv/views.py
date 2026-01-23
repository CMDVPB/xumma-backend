from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView

from abb.utils import get_user_company

from .models import PartRequest, StockBalance
from .serializers import (
    PartRequestCreateSerializer,
    PartRequestReadSerializer,
    PartRequestSerializer,
    StockBalanceSerializer,
    IssueDocumentSerializer,
)
from .services import reserve_request, issue_request, InventoryError


class StockBalanceListView(generics.ListAPIView):
    serializer_class = StockBalanceSerializer

    def get_queryset(self):
        qs = StockBalance.objects.select_related(
            "part", "location", "location__warehouse")
        part_id = self.request.query_params.get("part")
        warehouse_id = self.request.query_params.get("warehouse")

        if part_id:
            qs = qs.filter(part_id=part_id)
        if warehouse_id:
            qs = qs.filter(location__warehouse_id=warehouse_id)

        return qs


class PartRequestListCreateView(ListCreateAPIView):
    queryset = PartRequest.objects.all()
    serializer_class = PartRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user_company = get_user_company(self.request.user)
        return qs.filter(company=user_company)


class PartRequestDetailView(generics.RetrieveAPIView):
    queryset = PartRequest.objects.prefetch_related("lines__part")
    serializer_class = PartRequestReadSerializer


class ReserveRequestView(APIView):
    def post(self, request, pk: int):
        try:
            req = reserve_request(
                request_id=pk,
                actor_user=request.user,
                warehouse_id=request.data.get("warehouse_id"),
            )
        except InventoryError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            PartRequestReadSerializer(req).data,
            status=status.HTTP_200_OK,
        )


class IssueRequestView(APIView):
    def post(self, request, pk: int):
        try:
            doc = issue_request(request_id=pk, actor_user=request.user)
        except InventoryError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            IssueDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )
