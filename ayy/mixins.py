from django.shortcuts import get_object_or_404
from django.db.models import Q

from abb.utils import get_user_company
from ayy.models import CardProvider


class CardProviderAccessMixin:
    def get_provider(self):
        uf = self.kwargs["uf"]
        user = self.request.user

        company = get_user_company(user)

        return get_object_or_404(
            CardProvider,
            Q(is_system=True) | Q(company=company),
            uf=uf,
        )
