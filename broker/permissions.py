from rest_framework.permissions import BasePermission, SAFE_METHODS

from broker.helpers import get_user_role_in_point
from broker.models import Role
from broker.visibility import visible_points_for_user



class JobAccessPermission(BasePermission):
    """
    Combines:
    - Visibility control (read)
    - Role-based write restrictions
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        company = request.company

        # Admin full control
        if user.groups.filter(name__in=["level_admin", "level_manager"]).exists():
            return True

        # Visibility check first (read safety)
        allowed_points = visible_points_for_user(user, company)
        if not allowed_points.filter(id=obj.point_id).exists():
            return False

        # SAFE methods (GET, HEAD, OPTIONS)
        if request.method in SAFE_METHODS:
            return True

        # WRITE restrictions
        role = get_user_role_in_point(user, company, obj.point)

        # No membership
        if not role:
            return False

        # Leader → can update only own team jobs
        if role == Role.LEADER:
            return True

        # Broker → can update only if assigned
        if role == Role.BROKER:
            return obj.assigned_to_id == user.id

        return False