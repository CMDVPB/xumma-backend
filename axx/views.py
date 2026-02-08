from datetime import datetime, timedelta
from smtplib import SMTPException
from webbrowser import get
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
from django.http import FileResponse, Http404
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, CreateAPIView, \
    RetrieveUpdateDestroyAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser  # JSONParser
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated  # used for FBV

from abb.constants import LOAD_DOCUMENT_TYPES
from abb.permissions import IsSubscriptionActiveOrReadOnly
from abb.utils import get_user_company
from att.models import BankAccount, Contact, Contract, Person, VehicleUnit
from axx.models import Load, LoadDocument, TripAdvancePayment
from axx.serializers import LoadDocumentItemSerializer, TripAdvancePaymentChangeStatusSerializer, TripAdvancePaymentCreateSerializer, TripAdvancePaymentListSerializer
from axx.service import LoadDocumentService
from dff.serializers.serializers_other import ContactSerializer, ContractFKSerializer, ContractListSerializer

import logging
logger = logging.getLogger(__name__)


class ContactListCreate(ListCreateAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Contact.objects.filter(company__id=user_company.id)

            contact_persons = Person.objects.all()
            vehicle_units = VehicleUnit.objects.all()
            bank_accounts = BankAccount.objects.all()

            queryset = queryset.prefetch_related(
                Prefetch('contact_persons', queryset=contact_persons))

            queryset = queryset.prefetch_related(
                Prefetch('contact_vehicle_units', queryset=vehicle_units))

            queryset = queryset.prefetch_related(
                Prefetch('contact_bank_accounts', queryset=bank_accounts)).all()

            return queryset.distinct().order_by('-created_at')

        except Exception as e:
            logger.error(
                f'ERRORLOG3343 ContactListCreate get_queryset. ERROR: {e}')
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
        except Exception as e:
            logger.error(
                f'ERRORLOG3391 ContactListCreate perform_create. ERROR: {e}')
            serializer.save()


class ContactDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return Contact.objects.filter(company__id=user_company.id).distinct().order_by('-created_at')
        except Exception as e:
            print('E435', e)
            return Contact.objects.none()

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


class ContractListView(ListAPIView):
    serializer_class = ContractListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Contract.objects.filter(company__id=user_company.id)

            queryset = (queryset.select_related(
                'company',
                'contact',
                'reference_date'
            ))

            return queryset.order_by('-created_at')

        except Exception:
            logger.exception(
                'ERRORLOG3007 ContractListView get_queryset')
            return Contract.objects.none()


class TripAdvancePaymentListView(ListAPIView):
    serializer_class = TripAdvancePaymentListSerializer

    def get_queryset(self):
        trip_uf = self.kwargs['trip_uf']
        user_company = get_user_company(self.request.user)
        return TripAdvancePayment.objects.filter(
            company=user_company,
            trip__uf=trip_uf
        ).select_related(
            'currency', 'payment_method', 'status', 'created_by'
        )


class TripAdvancePaymentCreateView(CreateAPIView):
    serializer_class = TripAdvancePaymentCreateSerializer


class TripAdvancePaymentChangeStatusView(APIView):
    def post(self, request, uf):
        user_company = get_user_company(request.user)
        advance = get_object_or_404(
            TripAdvancePayment,
            uf=uf,
            company=user_company
        )

        serializer = TripAdvancePaymentChangeStatusSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']

        # enforce transitions
        allowed = {
            'requested': {'approved', 'rejected'},
            'approved': {'paid', 'cancelled'},
            'paid': set(),
            'rejected': set(),
        }

        if new_status.code not in allowed.get(
            advance.status.code, set()
        ):
            return Response(
                {'detail': 'Invalid status transition'},
                status=status.HTTP_400_BAD_REQUEST
            )

        advance.status = new_status

        if new_status.code == 'approved':
            advance.approved_at = timezone.now()

        if new_status.code == 'paid':
            advance.paid_at = timezone.now()

        advance.save()

        return Response({'status': 'ok'})


class TripAdvancePaymentDeleteView(DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return TripAdvancePayment.objects.filter(
            company=user_company
        )

    def perform_destroy(self, instance):
        if self.request.user.groups.filter(name='level_driver').exists():
            raise ValidationError('Drivers cannot delete advances')

        if instance.status.code != 'requested':
            raise ValidationError('Only requested advances can be deleted')

        instance.delete()


class GenerateLoadDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_uf, doc_type):
        load = get_object_or_404(Load, uf=load_uf)

        generation_data = {
            "amount": request.data.get("amount"),
            "notes": request.data.get("notes"),
            "currency_code": request.data.get("currencyCode"),
        }

        doc = LoadDocumentService.generate(
            load=load,
            doc_type=doc_type,
            user=request.user,
            runtime_data=generation_data
        )

        return Response({
            "id": doc.id,
            "doc_type": doc.doc_type,
            "version": doc.version,
            "url": doc.file.url,
        })


class LoadDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, load_uf):
        load = get_object_or_404(Load, uf=load_uf)

        docs = (
            LoadDocument.objects
            .filter(load=load, is_active=True)
        )

        docs_by_type = {doc.doc_type: doc for doc in docs}

        response = {}

        for doc_type in LOAD_DOCUMENT_TYPES:
            doc = docs_by_type.get(doc_type)

            if not doc:
                response[doc_type] = {"exists": False}
            else:
                data = {
                    "exists": True,
                    "id": doc.id,
                    "version": doc.version,
                    "uf": doc.uf,
                }
                response[doc_type] = LoadDocumentItemSerializer(data).data

        return Response(response)


class LoadDocumentProxyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uf):
        try:
            document = (
                LoadDocument.objects
                .select_related("load")
                .get(uf=uf, is_active=True)
            )
        except LoadDocument.DoesNotExist:
            raise Http404()

        user_company = get_user_company(request.user)

        # Company-level access control
        # if document.load.company and document.load.company != user_company:
        #     raise Http404()

        return FileResponse(
            document.file.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=document.file.name.split("/")[-1],
        )
