from rest_framework.permissions import BasePermission, SAFE_METHODS

from abb.utils import get_user_company
from broker.helpers import get_user_role_in_point
from broker.models import Role
from broker.visibility import visible_points_for_user


class JobAccessPermission(BasePermission):
    """
    Combines:
    - Visibility control (read)
    - Role-based write restrictions
    - Global broker restriction: only own jobs
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        company = get_user_company(user)

        # Admin / manager full control
        if user.groups.filter(name__in=["level_admin", "level_manager"]).exists():
            return True

        # Global broker restriction: only own jobs for all methods
        if user.groups.filter(name="level_broker").exists():
            return obj.assigned_to_id == user.id

        # Visibility check first
        allowed_points = visible_points_for_user(user, company)
        if not allowed_points.filter(id=obj.point_id).exists():
            return False

        # SAFE methods
        if request.method in SAFE_METHODS:
            return True

        role = get_user_role_in_point(user, company, obj.point)

        if not role:
            return False

        if role == Role.LEADER:
            return True

        if role == Role.BROKER:
            return obj.assigned_to_id == user.id

        return False
    

class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(
            name__in=["level_admin", "level_manager"]
        ).exists()
    

class BrokerDeletePermission(BasePermission):
    """
    Restrict deletion of invoiced jobs.
    Invoiced jobs can be deleted only by users in:
    - level_admin
    - level_manager
    - level_finance_leader
    """

    message = "You cannot delete this job because an invoice has already been issued."

    allowed_group_names = (
        "level_admin",
        "level_manager",
        "level_finance_leader",
    )

    def has_object_permission(self, request, view, obj):
        # only apply this rule to DELETE
        if request.method != "DELETE":
            return True

        # if job is not invoiced, allow delete
        if not obj.is_invoiced:
            return True

        return request.user.groups.filter(name__in=self.allowed_group_names).exists()