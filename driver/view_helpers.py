

from rest_framework.response import Response
from abb.utils import get_user_company
from driver.models import TripStop


def get_stop_or_404(request, uf):
    company = get_user_company(request.user)

    try:
        stop = TripStop.objects.select_related(
            "trip").get(uf=uf, company=company)
    except TripStop.DoesNotExist:
        return None, Response({"detail": "Stop not found"}, status=404)

    return stop, None
