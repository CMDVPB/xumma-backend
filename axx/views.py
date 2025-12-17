from datetime import datetime, timedelta
from smtplib import SMTPException
from django.utils import timezone
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Sum, Prefetch, Q, Case, When
from django.db.models.deletion import RestrictedError
from django.views.decorators.cache import cache_page
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, exceptions
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, CreateAPIView, \
    RetrieveUpdateDestroyAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser  # JSONParser
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated  # used for FBV

from abb.permissions import IsSubscriptionActiveOrReadOnly
from abb.utils import get_user_company
from att.models import Contact
from dff.serializers.serializers_other import ContactSerializer

import logging
logger = logging.getLogger(__name__)


class ContactListCreate(ListCreateAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    lookup_field = 'uf'
    http_method_names = ['head', 'get', 'post']

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Contact.objects.filter(company__id=user_company.id)

            # contact_persons = Person.objects.select_related(
            #     'owner').all()
            # vehicle_units = VehicleUnit.objects.select_related(
            #     'owner').all()
            # bank_accounts = BankAccount.objects.select_related(
            #     'owner').select_related('currency_code').all()

            # queryset = Contact.objects.select_related('owner').select_related(
            #     'countrycodelegal').select_related('countrycodepost')

            # queryset = queryset.prefetch_related(
            #     Prefetch('contact_persons', queryset=contact_persons))

            # queryset = queryset.prefetch_related(
            #     Prefetch('contact_vehicle_units', queryset=vehicle_units))

            # queryset = queryset.prefetch_related(
            #     Prefetch('contact_bank_accounts', queryset=bank_accounts)).all()

            return queryset.distinct().order_by('company_name')

        except Exception as e:
            print('E587', e)
            return Contact.objects.none()

    def post(self, request,  *args, **kwargs):
        request_obj = request.data.get('company_name', None).lower()
        if not self.get_queryset().filter(company_name__iexact=request_obj).exists():
            return self.create(request, *args, **kwargs)
        else:
            return Response(status=status.HTTP_409_CONFLICT)

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except:
            print('E269')
            serializer.save()


class ContactDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    http_method_names = ['head', 'get', 'put', 'patch', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return Contact.objects.filter(company__id=user_company.id).distinct()
        except:
            print('E435')
            return []

    def put(self, request, *args, **kwargs):
        # print('3637', )
        instance = self.get_object()
        request_obj = request.data.get('company_name', None)
        # print('4237', request_obj)

        if request_obj == None or (instance.company_name and instance.company_name.lower() == request_obj.lower()) or \
                not self.get_queryset().filter(company_name__iexact=request_obj.lower()).exists():
            return self.update(request, *args, **kwargs)
        else:
            return Response(status=status.HTTP_409_CONFLICT)

    def patch(self, request, *args, **kwargs):
        # print('3637', )
        instance = self.get_object()
        request_obj = request.data.get('company_name', None)
        # print('4237', request_obj)

        if request_obj == None or (instance.company_name and instance.company_name.lower() == request_obj.lower()) or \
                not self.get_queryset().filter(company_name__iexact=request_obj.lower()).exists():
            return self.partial_update(request, *args, **kwargs)
        else:
            return Response(status=status.HTTP_409_CONFLICT)

    def perform_update(self, serializer):
        try:
            serializer.save()
        except RestrictedError as e:
            raise ValidationError(
                {"detail": "entry_not_deleted_used_in_related_documents"}, code=400)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {'error': 'restricted'},
                status=status.HTTP_400_BAD_REQUEST
            )
