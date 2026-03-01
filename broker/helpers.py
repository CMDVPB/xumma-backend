from django.db.models import Q
from .models import PointMembership, PointOfService, TeamVisibilityGrant

def visible_points(user, company):
    base = PointOfService.objects.filter(
        company=company,
        point_memberships__user=user,
        point_memberships__is_active=True
    )

    grants = PointOfService.objects.filter(
        company=company,
        point_team_visibility_grants__user=user
    )

    return (base | grants).distinct()


def get_user_role_in_point(user, company, point):
    membership = PointMembership.objects.filter(
        company=company,
        user=user,
        point=point,
        is_active=True
    ).first()

    if not membership:
        return None

    return membership.role