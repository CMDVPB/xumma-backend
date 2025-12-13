import time
from datetime import datetime
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.db import IntegrityError
from django.db.models import QuerySet, Prefetch, Q, F
from django.core.exceptions import PermissionDenied
from djoser import signals
from djoser.compat import get_user_email
from djoser.email import ActivationEmail, ConfirmationEmail
from rest_framework import permissions, status, exceptions
from rest_framework import generics, mixins
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # used for FBV
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError


import logging

from abb.constants import ALLOWED_TYPE_ACCOUNT_GROUPS_TO_ADD
from abb.permissions import AddNewUserPermission, IsManager
from app.djoser_serializers import UserBaseCreateSerializer
from app.serializers import UserSerializer
logger = logging.getLogger(__name__)


User = get_user_model()


class UserManagerCreate(CreateAPIView):
    """ create manager only """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserBaseCreateSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = serializer.save()
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )

        type_group_to_add = self.request.data.get(
            'type_account', 'type_carrier')

        logger.info(
            f"INFOLOGAU004 user_id , create manager {user.email, type_group_to_add}")

        try:
            if type_group_to_add and (type_group_to_add in ALLOWED_TYPE_ACCOUNT_GROUPS_TO_ADD):
                Group.objects.get(name=type_group_to_add).user_set.add(user.id)
        except Exception as e:
            logger.error(
                f'ERRORLOG009 UserManagerCreate. perform_update. Error: {e}')
            pass

        context = {"user": user, "lang": user.lang or "en"}
        to = [get_user_email(user)]
        if settings.DJOSER.get('SEND_ACTIVATION_EMAIL', None):
            ActivationEmail(self.request, context,
                            template_name='dff/activation.html').send(to)

        elif settings.DJOSER.get('SEND_CONFIRMATION_EMAIL', None):
            ConfirmationEmail(self.request, context).send(to)


class UserCreate(CreateAPIView):
    ''' create regular user by manager only '''

    serializer_class = UserBaseCreateSerializer
    permission_classes = [IsAuthenticated, IsManager, AddNewUserPermission]

    def perform_create(self, serializer):
        manager_base_country = self.request.user.base_country
        user = serializer.save(base_country=manager_base_country)
        logger.info(
            f'AU1470 Create regular user by manager only manager: {self.request.user.email}, manager base country: {manager_base_country}, user: {user}')
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )

        context = {"user": user}
        to = [get_user_email(user)]
        if settings.DJOSER.get('SEND_ACTIVATION_EMAIL', None):

            # print('8888:', settings.DJOSER.get('EMAIL', None))
            ActivationEmail(self.request, context,
                            template_name='dff/activation.html').send(to)

        elif settings.DJOSER.get('SEND_CONFIRMATION_EMAIL', None):
            ConfirmationEmail(self.request, context).send(to)


class UserDetailSelf(generics.GenericAPIView, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    """ self get/update/delete user """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    # def get_queryset(self, *args, **kwargs):
    #     user_company = self.request.user.company_set.all().first()
    #     company_users = user_company.user.all()
    #     company_users_ids = [user.id for user in company_users]

    #     queryset = User.objects.filter(id__in=company_users_ids)

    #     print('4342', self.request,  len(queryset))

    #     return queryset

    def get_object(self):
        # Directly return the current user
        return self.request.user

    def get_queryset(self):
        # Ensure queryset only contains the current user
        return User.objects.filter(pk=self.request.user.pk)

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)

        try:
            refresh_token = request.COOKIES.get('refresh')
            refresh_token = RefreshToken(refresh_token)
            refresh_token.blacklist()

        except Exception as e:
            print('E006', e)
            pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            'access', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)
        response.delete_cookie(
            'refresh', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)

        return response
