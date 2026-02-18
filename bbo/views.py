from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from abb.utils import get_user_company
from bbo.service import get_top_customers

from .models import Notification, NotificationRead
from .serializers import NotificationSerializer, TopCustomersBlockSerializer


class NotificationListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        return (
            Notification.objects
            .filter(company=user_company)
            .order_by("-created_at")
        )


class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user_company = get_user_company(self.request.user)

        notification = get_object_or_404(
            Notification,
            pk=pk,
            company=user_company
        )

        NotificationRead.objects.get_or_create(
            notification=notification,
            user=request.user
        )

        return Response({"status": "ok"})


###### START APP TOP REVENUE CUSTOMERS ######
class TopCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user)

        response_data = []

        for period in (30, 90, 180):
            queryset = get_top_customers(period, user_company)

            response_data.append({
                "period": period,
                "customers": list(queryset)
            })

        serializer = TopCustomersBlockSerializer(response_data, many=True)
        return Response(serializer.data)

    ###### END APP TOP REVENUE CUSTOMERS ######
