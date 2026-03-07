from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from lync.views.lync_load import LoadSecretUpdateView, LoadSecretVerifyView
from lync.views.lync_user import LyncSequenceVerifyView, UserLyncSequenceView


urlpatterns = [

    path("verify-sequence/", LyncSequenceVerifyView.as_view()),

    path("user/sequence/", UserLyncSequenceView.as_view()),
    path("loads/verify/", LoadSecretVerifyView.as_view()),
    path("loads/<str:load_uf>/", LoadSecretUpdateView.as_view()),   

]

urlpatterns = format_suffix_patterns(urlpatterns)
