from django.urls import path, re_path
from rest_framework.urlpatterns import format_suffix_patterns

from app.views import (
    CustomProviderAuthView,
    CustomTokenObtainPairView,
    CustomCookieTokenRefreshView,
    CustomCookieVerifyView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    LogoutCookieView,
    LogoutTokenView,
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
    path('jwt/refresh/', CustomCookieTokenRefreshView.as_view()),
    path('jwt/verify/', CustomCookieVerifyView.as_view()),
    path('logout/', LogoutCookieView.as_view()),


    # token / mobile app
    path('jwt/token/verify/', CustomTokenVerifyView.as_view()),
    path('jwt/token/refresh/', CustomTokenRefreshView.as_view()),
    path('token/logout/', LogoutTokenView.as_view()),




    path('ex-rates-multi/', get_exchange_rates_multi_view,
         name='get-exchange-rates'),


    path("user/profile/", UserProfileView.as_view(), name="user-profile"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
