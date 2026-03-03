from rest_framework.exceptions import PermissionDenied

from abb.utils import get_user_company
from broker.visibility import visible_points_for_user

class CompanyScopedMixin:
    """
    Assumes request.user has .company or you resolve company via middleware.
    """

    def get_company(self):
        company = get_user_company(self.request.user)
        if not company:
            raise PermissionDenied("Company not resolved")
        return company
    



class JobVisibilityQuerysetMixin:

    def filter_queryset_by_visibility(self, queryset):
        user = self.request.user

        company = get_user_company(self.request.user)

        if user.groups.filter(name__in=["level_admin", "level_manager"]).exists():
            return queryset

        allowed_points = visible_points_for_user(user, company)

        return queryset.filter(point__in=allowed_points)