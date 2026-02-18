from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [


    path("notifications/", NotificationListAPIView.as_view(),
         name="notifications-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadAPIView.as_view(),
         name="notification-mark-read",
         ),

    path('analytics/top-customers/',
         TopCustomersView.as_view(), name='top-customers'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
