from rest_framework.permissions import BasePermission

from abb.utils import get_user_company


class IsCompanyAdmin(BasePermission):

    def has_object_permission(self, request, view, obj):

        user = request.user
        user_company = get_user_company(request.user)

        same_company = user_company.id == obj.company_id

        is_admin = user.level in [
            "level_admin",
            "level_manager",
            
        ]

        return same_company and is_admin