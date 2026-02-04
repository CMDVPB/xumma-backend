from django.urls import path, re_path
from rest_framework.urlpatterns import format_suffix_patterns

from app.views import (
    CustomProviderAuthView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    LogoutView,
    UserProfileView,
    get_exchange_rates_multi_view,
)

urlpatterns = [
    re_path(
        r'^o/(?P<provider>\S+)/$',
        CustomProviderAuthView.as_view(),
        name='provider-auth'
    ),
    path('jwt/create/', CustomTokenObtainPairView.as_view()),
    path('jwt/refresh/', CustomTokenRefreshView.as_view()),
    path('jwt/verify/', CustomTokenVerifyView.as_view()),
    path('logout/', LogoutView.as_view()),


    path('ex-rates-multi/', get_exchange_rates_multi_view,
         name='get-exchange-rates'),


    path("user/profile/", UserProfileView.as_view(), name="user-profile"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
