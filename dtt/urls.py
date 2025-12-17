from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from dtt.views import UserSettingsView, get_post_delete_user_smtp_settings, test_smtp_connection_view

urlpatterns = [

    path('smtp-test/', test_smtp_connection_view, name='smtp_test'),
    path('smtp-settings/', get_post_delete_user_smtp_settings, name='smtp_settings'),
    path('user-settings/', UserSettingsView.as_view(), name='user_settings'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
