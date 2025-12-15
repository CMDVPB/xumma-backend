
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
from rest_framework.permissions import IsAuthenticated

from abb.permissions import IsSubscriptionActiveOrReadOnly
from abb.utils import get_user_company
from app.models import Company
from att.models import TargetGroup
from dff.serializers.serializers_company import CompanySerializer
from dff.serializers.serializers_other import TargetGroupSerializer  # used for FBV

import logging
logger = logging.getLogger(__name__)


class TargetGroupListCreate(ListCreateAPIView):
    serializer_class = TargetGroupSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    lookup_field = 'uf'
    http_method_names = ['head', 'get', 'post']

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = TargetGroup.objects.filter(company__id=user_company.id)

            return queryset.distinct().order_by('group_name')
        except Exception as e:
            print('E553')
            return TargetGroup.objects.none()

    def post(self, request,  *args, **kwargs):
        request_obj = request.data.get('group_name', None).lower()
        if not self.get_queryset().filter(group_name__iexact=request_obj).exists():

            return self.create(request, *args, **kwargs)

        else:
            raise exceptions.ValidationError(detail='not_unique')

    def perform_create(self, serializer):
        try:
            user_company = get_user_company(self.request.user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG241 TargetGroupListCreate. perform_create. Error: {e}')
            serializer.save()


class TargetGroupDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = TargetGroupSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    http_method_names = ['head', 'get', 'patch', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return TargetGroup.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG519 TargetGroupDetail. get_queryset. Error: {e}')
            return TargetGroup.objects.none()

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        request_obj = request.data.get('group_name', None).lower()
        # print('3897', request_obj)

        if (instance.group_name.lower() == request_obj) or \
                not self.get_queryset().filter(group_name__iexact=request_obj).exists():

            return self.partial_update(request, *args, **kwargs)

        else:
            raise exceptions.ValidationError(detail='not_unique',)


class CompanyDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySerializer

    def get_queryset(self):
        try:
            queryset = Company.objects.filter(
                user=self.request.user).distinct()

            return queryset
        except Exception as e:
            logger.error(
                f'ERRORLOG357 CompanyDetail. get_queryset. Error: {e}')

            return Company.objects.none()

    def get_object(self):
        try:
            return self.get_queryset().first()
        except:
            raise exceptions.NotFound()

    def delete(self, request, pk, format=None):
        company = self.get_object(pk)
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
