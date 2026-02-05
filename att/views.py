from django.utils.timezone import now
from django.db import transaction
import math
from django.conf import settings
from datetime import datetime
from django.db.models import QuerySet, Prefetch, Q, F
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.http import FileResponse, Http404
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.generics import (CreateAPIView, ListAPIView, ListCreateAPIView,
                                     UpdateAPIView, RetrieveUpdateDestroyAPIView, DestroyAPIView)
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from abb.constants import DOCUMENT_STATUS_CHOICES
from abb.models import BodyType, Incoterm, ModeType, StatusType
from abb.pagination import LimitResultsSetPagination
from abb.utils import get_user_company, is_valid_queryparam
from app.models import CategoryGeneral, TypeGeneral
from att.models import Contact, ContactStatus, EmissionClass, RouteSheetNumber, RouteSheetStockBatch, VehicleBrand, Vehicle, VehicleDocument
from att.serializers import BodyTypeSerializer, CategoryGeneralSerializer, ContactStatusSerializer, ContactStatusUpdateSerializer, EmissionClassSerializer, IncotermSerializer, ModeTypeSerializer, RouteSheetStockBatchSerializer, StatusTypeSerializer, TypeGeneralSerializer, \
    VehicleBrandSerializer, VehicleDocumentSerializer, VehicleSerializer


import logging

from att.services import update_contact_status_service
logger = logging.getLogger(__name__)


class TypeGeneralListView(ListAPIView):
    serializer_class = TypeGeneralSerializer

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return (TypeGeneral.objects
                    .filter(
                        Q(is_system=True) |
                        Q(company_id=user_company.id)
                    )
                    .order_by('serial_number')
                    .distinct())

        except Exception as e:
            logger.error(
                f'ERRORLOG509 TypeGeneralListView. get_queryset. Error: {e}')
            return TypeGeneral.objects.none()

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class CategoryGeneralListView(ListAPIView):
    serializer_class = CategoryGeneralSerializer

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return (CategoryGeneral.objects
                    .filter(
                        Q(is_system=True) |
                        Q(company_id=user_company.id)
                    )
                    .order_by('serial_number')
                    .distinct())

        except Exception as e:
            logger.error(
                f'ERRORLOG507 CategoryGeneralListView. get_queryset. Error: {e}')
            return CategoryGeneral.objects.none()

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class StatusTypeListView(ListAPIView):
    serializer_class = StatusTypeSerializer
    queryset = StatusType.objects.all().order_by('serial_number')

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class IncotermListView(ListAPIView):
    serializer_class = IncotermSerializer
    queryset = Incoterm.objects.all().order_by('serial_number')

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ModeTypeListView(ListAPIView):
    serializer_class = ModeTypeSerializer
    queryset = ModeType.objects.all().order_by('serial_number')

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class BodyTypeListView(ListAPIView):
    queryset = BodyType.objects.all().order_by('serial_number')
    serializer_class = BodyTypeSerializer

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class EmissionClassListView(ListAPIView):
    serializer_class = EmissionClassSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # print('2358', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = (EmissionClass.objects
                        .filter(
                            Q(is_system=True) |
                            Q(company_id=user_company.id)
                        )
                        .order_by('serial_number'))

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG239 EmissionClassListView. get_queryset. Error: {e}')
            return EmissionClass.objects.none()

    # @method_decorator(cache_page(60*60*24))

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class VehicleBrandListView(ListAPIView):
    serializer_class = VehicleBrandSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # print('2358', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = VehicleBrand.objects.filter(company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG235 VehicleBrandListView. get_queryset. Error: {e}')
            return VehicleBrand.objects.none()

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class VehicleCreateView(CreateAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return Vehicle.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG573 VehicleCompanyCreate. get_queryset. Error: {e}')
            return Vehicle.objects.none()

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG575 VehicleCompanyCreate. perform_create. Error: {e}')
            serializer.save()


class VehicleListView(ListAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-date_registered']

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            qs = Vehicle.objects.filter(
                company__id=user_company.id)

            qs = qs.prefetch_related(
                'vehicle_documents',
                'vehicle_documents__document_type'
            )

            return qs
        except Exception as e:
            logger.error(
                f'ERRORLOG735 VehicleCompanyListView. get_queryset. Error: {e}')
            return Vehicle.objects.none()

    def filter_queryset(self, qs: QuerySet, **kwargs):
        # print('4960',)

        qs = super().filter_queryset(queryset=qs, **kwargs)

        try:
            vehicle_type = self.request.query_params.get('vehicleType')
            is_service = self.request.query_params.get('isService')

            if is_valid_queryparam(vehicle_type):
                if vehicle_type == 'tractor':
                    qs = qs.filter(Q(vehicle_type='tractor') |
                                   Q(vehicle_type='truck'))
                elif vehicle_type == 'trailer':
                    qs = qs.filter(vehicle_type='trailer')

            if is_valid_queryparam(is_service):
                if is_service == '0':
                    qs = qs.filter(is_service=True)

            # print('4968', queryset.count())

            return qs.distinct().order_by('-created_at')

        except Exception as e:
            logger.error(
                f'ERRORLOG7535 VehicleCompanyListView. filter_queryset. Error: {e}')
            return qs


class VehicleDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VehicleSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            print('6800', self.request.user)
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Vehicle.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG549 VehicleCompanyDetailView. get_queryset. Error: {e}')
            return Vehicle.objects.none()

    # def patch(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     try:
    #         contact_uf = request.data.get('contact', None)
    #         request_obj = request.data.get('reg_number', None).lower()
    #         contact = Contact.objects.get(uf=contact_uf)
    #         contact_vehicle_units = [i.reg_number.lower()
    #                                  for i in contact.contact_vehicle_units.all().exclude(uf=instance.uf)]
    #         if not request_obj in contact_vehicle_units:
    #             return self.update(request, *args, **kwargs)
    #         else:
    #             return Response(status=status.HTTP_409_CONFLICT)
    #     except Exception as e:
    #         logger.error(f'EV549 VehicleUnitDetail. put. Error: {e}')
    #         return Response(status=status.HTTP_400_BAD_REQUEST)


class RouteSheetStockBatchListCreateView(ListCreateAPIView):
    serializer_class = RouteSheetStockBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = RouteSheetStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG365 RouteSheetStockBatchView. get_queryset. Error: {e}')
            return RouteSheetStockBatch.objects.none()


class RouteSheetStockBatchDetailsView(RetrieveUpdateDestroyAPIView):
    serializer_class = RouteSheetStockBatchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = RouteSheetStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG367 RouteSheetStockBatchView. get_queryset. Error: {e}')
            return RouteSheetStockBatch.objects.none()


def reserve_trip_number(customer):
    with transaction.atomic():
        number = (
            RouteSheetNumber.objects
            .select_for_update(skip_locked=True)
            .filter(customer=customer, status=DOCUMENT_STATUS_CHOICES[0][0])
            .order_by("number")
            .first()
        )

        if not number:
            raise ValueError("No free trip numbers")

        number.status = DOCUMENT_STATUS_CHOICES[1][0]
        number.reserved_at = now()
        number.save(update_fields=["status", "reserved_at"])

        return number


class VehicleDocumentCreateView(CreateAPIView):
    queryset = VehicleDocument.objects.all()
    serializer_class = VehicleDocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)


class VehicleDocumentUpdateView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = VehicleDocument.objects.all()
    serializer_class = VehicleDocumentSerializer
    parser_classes = (MultiPartParser, FormParser)


class VehicleDocumentFileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, uf):
        try:
            doc = VehicleDocument.objects.get(uf=uf)
        except VehicleDocument.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if doc.file:
            doc.file.delete(save=False)
            doc.file = None
            doc.save(update_fields=['file'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleDocumentListView(ListAPIView):
    serializer_class = VehicleDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = VehicleDocument.objects.all()
        vehicle_id = self.request.query_params.get('vehicle')

        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)

        return qs


class ContactStatusListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactStatusSerializer

    def get_queryset(self):
        qs = ContactStatus.objects.filter(is_active=True).order_by("severity")
        return qs


class ContactStatusUpdateAPIView(APIView):
    """
    Update contact status and create history record
    """

    def patch(self, request, uf):
        user_company = get_user_company(request.user)
        contact = get_object_or_404(
            Contact.objects.select_related("status"),
            uf=uf,
            company=user_company
        )

        serializer = ContactStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_contact_status_service(
            contact=contact,
            status=serializer.validated_data["status"],
            user=request.user,
            reason=serializer.validated_data.get("reason")
        )

       # IMPORTANT: refresh relation after service
        contact.refresh_from_db(fields=["status"])

        return Response(
            {
                "id": contact.id,
                "status": ContactStatusSerializer(contact.status).data,
            },
            status=status.HTTP_200_OK
        )


class VehicleDocumentFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uf):
        try:
            doc = VehicleDocument.objects.get(uf=uf)
        except VehicleDocument.DoesNotExist:
            raise Http404

        if not doc.file:
            raise Http404

        return FileResponse(
            doc.file.open('rb'),
            as_attachment=True,
            filename=doc.file.name.split('/')[-1]
        )
