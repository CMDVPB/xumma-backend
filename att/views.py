import math
from django.conf import settings
from datetime import datetime
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView, DestroyAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView  # exception_handler
from rest_framework_simplejwt.authentication import JWTAuthentication  # used for FBV
from rest_framework_simplejwt.exceptions import InvalidToken  # used for FBV
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated

from abb.models import BodyType, Incoterm, ModeType, StatusType
from abb.pagination import LimitResultsSetPagination
from abb.utils import get_user_company
from att.models import EmissionClass, VehicleBrand, VehicleCompany
from att.serializers import BodyTypeSerializer, EmissionClassdSerializer, IncotermSerializer, ModeTypeSerializer, StatusTypeSerializer, VehicleBrandSerializer, VehicleCompanySerializer


import logging
logger = logging.getLogger(__name__)


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
    serializer_class = EmissionClassdSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # print('2358', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = EmissionClass.objects.filter(
                company__id=user_company.id)

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


class VehicleCompanyCreateView(CreateAPIView):
    serializer_class = VehicleCompanySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['post']

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return VehicleCompany.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG573 VehicleCompanyCreate. get_queryset. Error: {e}')
            return VehicleCompany.objects.none()

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG575 VehicleCompanyCreate. perform_create. Error: {e}')
            serializer.save()


class VehicleCompanyListView(ListAPIView):
    serializer_class = VehicleCompanySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = VehicleCompany.objects.filter(
                company__id=user_company.id)

            return queryset.distinct().order_by('-id')
        except Exception as e:
            logger.error(
                f'ERRORLOG735 VehicleCompanyListView. get_queryset. Error: {e}')
            return VehicleCompany.objects.none()


class VehicleCompanyDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = VehicleCompanySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            print('6800', self.request.user)
            user = self.request.user
            user_company = get_user_company(user)
            queryset = VehicleCompany.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG549 VehicleCompanyDetailView. get_queryset. Error: {e}')
            return VehicleCompany.objects.none()

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
