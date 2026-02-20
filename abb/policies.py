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
