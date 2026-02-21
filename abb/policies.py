from django.db.models import Q

from abb.utils import get_user_company
from .roles import *


class PolicyFilteredQuerysetMixin:

    policy_class = None

    def get_base_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        if self.policy_class is None:
            raise RuntimeError("policy_class must be defined")

        qs = self.get_base_queryset()
        return self.policy_class.scope_queryset(self.request.user, qs)


class VehicleCheckListPolicy:

    @staticmethod
    def scope_queryset(user, qs):
        roles = get_user_roles(user)

        print('8552', roles)

        if ROLE_ADMIN in roles or ROLE_MANAGER in roles or ROLE_DISPATCHER in roles:
            print('8556', roles)
            return qs

        if ROLE_DRIVER in roles:
            print('8558', roles)
            return qs.filter(driver=user)

        return qs.none()

    @staticmethod
    def can_view(user):
        roles = get_user_roles(user)
        return bool(
            {ROLE_ADMIN, ROLE_MANAGER, ROLE_DISPATCHER, ROLE_DRIVER} & roles
        )


class DriverReportPolicy:

    @staticmethod
    def scope_queryset(user, qs):
        roles = get_user_roles(user)

        print('3848', roles)

        if ROLE_ADMIN in roles or ROLE_MANAGER in roles or ROLE_DISPATCHER in roles:
            print('3850', roles)
            return qs

        if ROLE_DRIVER in roles:
            print('3850', roles)
            return qs.filter(driver=user)

        return qs.none()

    @staticmethod
    def can_view(user):
        roles = get_user_roles(user)
        return bool(
            {ROLE_ADMIN, ROLE_MANAGER, ROLE_DISPATCHER, ROLE_DRIVER} & roles
        )


class ItemForItemCostPolicy:

    @staticmethod
    def scope_queryset(user, qs):
        user_company = get_user_company(user)
        return qs.filter(
            Q(company=user_company) | Q(is_system=True)
        )


class ItemCostPolicy:

    @staticmethod
    def scope_queryset(user, qs):
        roles = get_user_roles(user)

        user_company = get_user_company(user)

        ### HARD TENANT WALL ###
        qs = qs.filter(company=user_company)

        if ROLE_ADMIN in roles or ROLE_MANAGER in roles or ROLE_DISPATCHER in roles or ROLE_ACCOUNTANT in roles:
            return qs

        if ROLE_DRIVER in roles:
            return qs.filter(created_by=user)

        return qs.none()

    @staticmethod
    def can_create(user, trip):
        roles = get_user_roles(user)

        if ROLE_DRIVER in roles:
            return not trip.is_locked

        if ROLE_ADMIN in roles or ROLE_MANAGER in roles or ROLE_DISPATCHER in roles:
            return not trip.is_locked

        return False

    @staticmethod
    def can_modify(user, obj):
        roles = get_user_roles(user)

        if obj.trip.is_locked:
            return False

        if ROLE_ADMIN in roles or ROLE_MANAGER in roles or ROLE_DISPATCHER in roles:
            return True

        if ROLE_DRIVER in roles:
            return obj.created_by == user

        return False

    @staticmethod
    def can_view(user):
        roles = get_user_roles(user)
        return bool(
            {ROLE_ADMIN, ROLE_MANAGER, ROLE_DISPATCHER,
                ROLE_DRIVER, ROLE_ACCOUNTANT} & roles
        )


class TypeCostPolicy:

    @staticmethod
    def scope_queryset(user, qs):
        user_company = get_user_company(user)
        return qs.filter(
            Q(company=user_company) | Q(is_system=True)
        )
