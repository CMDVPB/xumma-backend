
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Exists, OuterRef, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView, GenericAPIView, \
    UpdateAPIView, DestroyAPIView
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response
from rest_framework import status

from att.models import Vehicle
from baa.models import VehicleChecklist, VehicleChecklistAnswer, VehicleChecklistItem, VehicleChecklistPhoto, VehicleEquipment
from baa.serializers import VehicleChecklistAnswerSerializer, VehicleChecklistItemSerializer, VehicleChecklistPhotoSerializer, VehicleChecklistSerializer, VehicleEquipmentSerializer


class StartVehicleChecklistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_uf):
        vehicle = get_object_or_404(Vehicle, uf=vehicle_uf)

        checklist = VehicleChecklist.objects.create(
            vehicle=vehicle,
            driver=request.user,
            company=vehicle.company,
        )

        items = VehicleChecklistItem.objects.filter(is_active=True)

        VehicleChecklistAnswer.objects.bulk_create([
            VehicleChecklistAnswer(
                checklist=checklist,
                item=item,
                is_ok=True
            )
            for item in items
        ])

        return Response(
            VehicleChecklistSerializer(
                checklist, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )


class VehicleChecklistAnswerAPIView(UpdateAPIView):
    queryset = VehicleChecklistAnswer.objects.all()
    serializer_class = VehicleChecklistAnswerSerializer
    permission_classes = [IsAuthenticated]


class VehicleChecklistPhotoCreateAPIView(CreateAPIView):
    serializer_class = VehicleChecklistPhotoSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(
            answer_id=self.kwargs["answer_id"],
            company=self.request.user.company if hasattr(
                self.request.user, "company") else None,
        )


class FinishChecklistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, checklist_id):
        checklist = get_object_or_404(VehicleChecklist, id=checklist_id)

        checklist.finished_at = timezone.now()
        checklist.is_completed = True
        checklist.mileage = request.data.get("mileage")
        checklist.general_comment = request.data.get("general_comment")
        checklist.save()

        return Response({"status": "completed"})


class VehicleChecklistTemplateAPIView(ListAPIView):
    serializer_class = VehicleChecklistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VehicleChecklistItem.objects.filter(is_active=True).order_by("order")


class VehicleChecklistDetailAPIView(RetrieveAPIView):
    queryset = VehicleChecklist.objects.select_related(
        "vehicle", "driver"
    ).prefetch_related(
        "checklist_answers__answer_photos"
    )
    serializer_class = VehicleChecklistSerializer
    permission_classes = [IsAuthenticated]


class VehicleEquipmentListCreateAPIView(ListCreateAPIView):
    serializer_class = VehicleEquipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VehicleEquipment.objects.filter(
            vehicle_id=self.kwargs["vehicle_id"]
        )

    def perform_create(self, serializer):
        serializer.save(
            vehicle_id=self.kwargs["vehicle_id"],
            company=self.request.user.company if hasattr(
                self.request.user, "company") else None,
            last_updated_by=self.request.user,
        )


class VehicleEquipmentUpdateAPIView(UpdateAPIView):
    queryset = VehicleEquipment.objects.all()
    serializer_class = VehicleEquipmentSerializer
    permission_classes = [IsAuthenticated]
