
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Exists, OuterRef, Q
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.generics import (CreateAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView, GenericAPIView,
                                     UpdateAPIView, DestroyAPIView)
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from abb.policies import PolicyFilteredQuerysetMixin, VehicleCheckListPolicy
from abb.utils import get_user_company
from att.models import Vehicle
from axx.models import Trip
from baa.models import VehicleChecklist, VehicleChecklistAnswer, VehicleChecklistItem, VehicleChecklistPhoto, VehicleEquipment
from baa.serializers import (VehicleChecklistAnswerSerializer, VehicleChecklistItemSerializer, VehicleChecklistListSerializer,
                             VehicleChecklistPhotoSerializer, VehicleChecklistSerializer, VehicleEquipmentSerializer)


class VehicleChecklistListAPIView(PolicyFilteredQuerysetMixin, ListAPIView):
    """
    List all vehicle checklists (history + active).
    """
    serializer_class = VehicleChecklistListSerializer
    permission_classes = [IsAuthenticated]
    policy_class = VehicleCheckListPolicy

    def get_base_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)

        qs = VehicleChecklist.objects.select_related(
            "vehicle", "driver"
        ).prefetch_related(
            "checklist_answers"
        )

        qs = qs.filter(company=user_company)

        return qs.order_by("-started_at")


class StartVehicleChecklistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_uf):
        vehicle = get_object_or_404(Vehicle, uf=vehicle_uf)
        inspection_type = request.data.get("inspection_type")

        user_company = get_user_company(request.user)

        # GUARDS
        if vehicle.company != user_company:
            return Response({"error": "Invalid vehicle"}, status=403)
        if not inspection_type:
            return Response({"error": "inspection_type required"}, status=400)

        if inspection_type not in ["departure", "arrival"]:
            return Response(
                {"error": "Invalid inspection_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip = Trip.objects.filter(
            drivers=request.user, date_end__isnull=True).first()

        if not trip:
            return Response({"error": "No active trip"}, status=400)

        existing = VehicleChecklist.objects.filter(
            trip=trip,
            vehicle=vehicle,
            driver=request.user,
            inspection_type=inspection_type,
            is_completed=False,
        ).order_by("-started_at").first()

        if existing:
            return Response(
                VehicleChecklistSerializer(
                    existing, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        checklist = VehicleChecklist.objects.create(
            trip=trip,
            vehicle=vehicle,
            driver=request.user,
            company=vehicle.company,
            inspection_type=inspection_type,
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
    permission_classes = [IsAuthenticated]
    serializer_class = VehicleChecklistAnswerSerializer
    queryset = VehicleChecklistAnswer.objects.all()


class VehicleChecklistPhotoCreateAPIView(CreateAPIView):
    serializer_class = VehicleChecklistPhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        answer_id = self.kwargs["answer_id"]
        serializer.save(answer_id=answer_id)


class FinishChecklistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, checklist_id):
        checklist = get_object_or_404(VehicleChecklist, id=checklist_id)

        checklist.finished_at = timezone.now()
        checklist.is_completed = True

        mileage = request.data.get("mileage")
        if mileage is not None:
            checklist.mileage = mileage

        comment = request.data.get("general_comment")
        if comment is not None:
            checklist.general_comment = comment

        checklist.save()

        trip = checklist.trip

        if trip:
            update_fields = []

            if checklist.inspection_type == "departure":
                if not trip.departure_inspection_completed:
                    trip.departure_inspection_completed = True
                    update_fields.append("departure_inspection_completed")

            elif checklist.inspection_type == "arrival":
                if not trip.arrival_inspection_completed:
                    trip.arrival_inspection_completed = True
                    update_fields.append("arrival_inspection_completed")

            if update_fields:
                trip.save(update_fields=update_fields)

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
        "checklist_answers__item",
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


class InspectionFileProxyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uf):
        try:
            photo = VehicleChecklistPhoto.objects.select_related(
                "answer__checklist"
            ).get(uf=uf)
        except VehicleChecklistPhoto.DoesNotExist:
            raise Http404()

        user_company = get_user_company(request.user)

        if (
            photo.answer.checklist.company
            and user_company != photo.answer.checklist.company
        ):
            raise Http404()

        return FileResponse(
            photo.image.open(),
            content_type="image/jpeg",
        )


class InspectionFileUploadView(CreateAPIView):
    serializer_class = VehicleChecklistPhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        serializer.save(answer_id=self.request.data.get("answer_id"))


class InspectionFileDeleteView(DestroyAPIView):
    queryset = VehicleChecklistPhoto.objects.all()
    permission_classes = [IsAuthenticated]
