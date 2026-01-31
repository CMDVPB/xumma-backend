
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)
from django.conf import settings
from django.conf.urls.static import static

from django.http import HttpResponse

urlpatterns = [
    path('admin-liv-umma/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),

    path('api/', include('abb.urls')),
    path('api/', include('app.urls')),
    path('api/', include('att.urls')),
    path('api/', include('auu.urls')),
    path('api/', include('avv.urls')),
    path('api/', include('axx.urls')),
    path('api/', include('ayy.urls')),
    path('api/', include('azz.urls')),
    path('api/', include('bch.urls')),
    path('api/', include('cld.urls')),
    path('api/', include('dff.urls')),
    path('api/', include('dtt.urls')),
    path('api/', include('eff.urls')),
    path('api/', include('eml.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
