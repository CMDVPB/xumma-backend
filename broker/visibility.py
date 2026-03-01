from broker.models import PointOfService

def visible_points_for_user(user, company):
    """
    Returns queryset of points the user is allowed to see.
    """

    if user.groups.filter(name="level_admin").exists():
        return PointOfService.objects.filter(company=company)

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