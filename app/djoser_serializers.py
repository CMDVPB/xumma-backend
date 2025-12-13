from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from djoser.compat import get_user_email_field_name
from djoser.conf import settings as djoser_settings
from djoser.serializers import UserCreateSerializer


import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class UserBaseCreateSerializer(UserCreateSerializer):

    def create(self, validated_data):
        # print('6633', kwargs)
        user_create_email = validated_data.get('email', None)
        is_user_registered = User.objects.filter(email=user_create_email)

        if not is_user_registered:
            try:
                user = self.perform_create(validated_data)
            except IntegrityError:
                self.fail("cannot_create_user")

            return user

        else:
            print('6677')
            raise PermissionDenied(
                detail='user with this email already exists')

    def perform_create(self, validated_data):
        # print('6688:', validated_data)
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)

            if settings.DJOSER.get('SEND_ACTIVATION_EMAIL', None):
                user.is_active = False

            user.save(update_fields=["is_active", ])
        return user

    class Meta:
        model = User
        fields = ('email', 'password', 'lang', 'base_country', 'uf')
        extra_kwargs = {
            'type_account': {'type_account': 'type_account'},
        }


class UserFunctionsMixin:
    # @sync_to_async  # added this line
    def get_user(self, is_active=True):
        print('DJ4748', self.data)
        try:
            user = User._default_manager.get(
                is_active=is_active, ** {self.email_field: self.data.get(self.email_field, "")},
            )
            if user.has_usable_password():
                return user
        except User.DoesNotExist:
            print('E475 User does not exist', self.data)
            pass
        if (
            djoser_settings.PASSWORD_RESET_SHOW_EMAIL_NOT_FOUND
            or djoser_settings.USERNAME_RESET_SHOW_EMAIL_NOT_FOUND
        ):
            self.fail("email_not_found")


class SendEmailResetSerializer(serializers.Serializer, UserFunctionsMixin):
    default_error_messages = {
        "email_not_found": djoser_settings.CONSTANTS.messages.EMAIL_NOT_FOUND
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email_field = get_user_email_field_name(User)
        self.fields[self.email_field] = serializers.EmailField()
