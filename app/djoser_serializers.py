from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from djoser.compat import get_user_email_field_name
from djoser.conf import settings as djoser_settings
from djoser.serializers import UserCreateSerializer


import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class UserBaseCreateSerializer(UserCreateSerializer):

    level = serializers.SerializerMethodField()

    ALLOWED_LEVELS = {
        "level_manager",
        "level_finance",
        "level_leader",
        "level_dispatcher",
        "level_driver",
    }

    def get_level(self, user):
        group = user.groups.filter(name__startswith="level_").first()
        return group.name if group else None

    def _assign_group(self, user, level):
        if level not in self.ALLOWED_LEVELS:
            raise serializers.ValidationError("Invalid user level")

        group = Group.objects.filter(name=level).first()
        if not group:
            raise serializers.ValidationError("Group does not exist")

        user.groups.add(group)

    def create(self, validated_data):
        # print('6633', kwargs)
        user_create_email = validated_data.get('email', None)

        if User.objects.filter(email=user_create_email).exists():
            raise PermissionDenied(
                detail='user with this email already exists')

        request = self.context["request"]
        level = request.data.get("level")

        try:
            user = self.perform_create(validated_data)

            # Assign company (manager → user)
            manager_company = request.user.company_set.first()
            if manager_company:
                user.company_set.add(manager_company)

            # Assign group
            if level:
                self._assign_group(user, level)

        except IntegrityError:
            self.fail("cannot_create_user")

        return user

    def perform_create(self, validated_data):
        # print('6688:', validated_data)
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)

            if settings.DJOSER.get('SEND_ACTIVATION_EMAIL', None):
                user.is_active = False

            user.save(update_fields=["is_active"])
        return user

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'date_registered', 'date_of_birth', 'personal_id', 'uf',
                  'lang', 'base_country',
                  'level',
                  )
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
