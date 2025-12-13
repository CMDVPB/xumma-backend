from django.contrib.auth.models import Group
from rest_framework import permissions

from abb.utils import get_company_manager, get_user_company, get_is_company_subscription_active, get_company_users

import logging
logger = logging.getLogger(__name__)


class IsManager(permissions.BasePermission):
    """
    Custom permission to only allow only Managers to perform an action.
    """

    def has_permission(self, request, view):
        # print('6400', request.user)
        return request.user and request.user.groups.filter(name='level_manager').exists()


class isTeamLeader(permissions.BasePermission):

    def has_team_leader_permission(self, request, view, obj):
        if request.user.is_team_leader:
            return True
        return False


class AddNewUserPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        level_group_name = 'level_manager'

        try:
            logger.info(
                f'PS2400 AddNewUserPermission, manager: {request.user}')

            if not request.user.groups.filter(name__exact=level_group_name).exists():
                return False
            else:
                return True

        except Exception as e:
            logger.error(f'EP445 AddNewUserPermission, error: {e}')
            return False


class HasGroupPermission(permissions.BasePermission):
    """
    Ensure user is in required groups.
    """

    def has_permission(self, request, view):
        # Get a mapping of methods -> required group.
        required_groups_mapping = getattr(view, "required_groups", {})

        # Determine the required groups for this particular request method.
        required_groups = required_groups_mapping.get(request.method, [])

        # Return True if the user has all the required groups or is staff.
        return all([self.is_in_group(request.user, group_name) if group_name != "__all__" else True for group_name in required_groups]) \
            or (request.user and request.user.is_staff)

    def is_in_group(self, user, group_name):
        """
        Takes a user and a group name, and returns `True` if the user MANAGER is in that group.
        """
        # if user !
        try:
            user_company = get_user_company(user)
            company_manager = get_company_manager(user_company)

            # min type_fowarder or type_carrier
            if group_name == 'type_forwarder':
                return Group.objects.get(name=group_name).user_set.filter(id=company_manager.id).exists() \
                    or Group.objects.get(name='type_carrier').user_set.filter(id=company_manager.id).exists()

            # min type_shipper, type_fowarder or type_carrier
            if group_name == 'type_shipper':
                return Group.objects.get(name=group_name).user_set.filter(id=company_manager.id).exists() \
                    or Group.objects.get(name='type_forwarder').user_set.filter(id=company_manager.id).exists() \
                    or Group.objects.get(name='type_carrier').user_set.filter(id=company_manager.id).exists()

            return Group.objects.get(name=group_name).user_set.filter(id=company_manager.id).exists()
        except Group.DoesNotExist:
            return None


class IsSubscriptionActiveOrReadOnly(permissions.BasePermission):
    message = "Your subscription has expired."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:

            return True

        try:
            user = request.user
            user_company = get_user_company(user)

            is_company_subscription_active = get_is_company_subscription_active(
                user_company)

            if not is_company_subscription_active:
                return False

            return True

        except Exception as e:
            logger.error(
                f'EP375 IsSubscriptionActiveOrReadOnly, error: {e}')
            return False

    def has_permission(self, request, view):
        #### Always allow safe (read-only) methods ###
        if request.method in permissions.SAFE_METHODS:
            return True

        try:
            user = request.user
            user_company = get_user_company(user)
            is_company_subscription_active = get_is_company_subscription_active(
                user_company)
            return is_company_subscription_active
        except Exception as e:
            logger.error(f"EP377 IsSubscriptionActiveOrReadOnly, error: {e}")
            return False


class AssignedUserOrManagerOrReadOnly(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        level_group_name = 'level_manager'

        try:
            company_users = get_company_users(request.user)

            if (obj.assigned_user == request.user) or \
                (obj.assigned_user != request.user and (request.method in permissions.SAFE_METHODS or not obj.is_locked)) or \
                (obj.is_locked and obj.assigned_user is None) or \
                    (obj.assigned_user in company_users and request.user.groups.filter(name__exact=level_group_name).exists()):

                return True

            logger.info(f'PM4830 AssignedUserOrManagerOrReadOnly.')

            return False
        except Exception as e:
            logger.error(
                f'EP565 AssignedUserOrManagerOrReadOnly, error: {e}')
            return False


class AssignedUserManagerOrReadOnlyIfLocked(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        level_group_name = 'level_manager'

        try:
            logger.info(
                f'PS5802 AssignedUserManagerOrReadOnlyIfLocked, user: {request.user}, assigned user: {obj.assigned_user}')

            company_users = get_company_users(request.user)

            if (not obj.is_locked) or (obj.assigned_user == request.user) or \
                    (obj.is_locked and request.method in permissions.SAFE_METHODS) or (obj.is_locked and obj.assigned_user is None) or \
                (obj.assigned_user in company_users and request.user.groups.filter(name__exact=level_group_name).exists() ):
                # print('5810')
                return True

            return False
        except Exception as e:
            logger.error(
                f'EP573 AssignedUserManagerOrReadOnlyIfLocked, error: {e}')
            return False
