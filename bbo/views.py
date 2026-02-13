from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from abb.utils import get_user_company

from .models import Notification, NotificationRead
from .serializers import NotificationSerializer


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
