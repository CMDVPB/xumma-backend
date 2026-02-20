from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [

    path("pois/", POIListCreateAPIView.as_view()),
    path("pois/<int:pk>/", POIRetrieveUpdateDestroyAPIView.as_view()),

    path("pois/<int:poi_id>/reviews/", POIReviewListCreateAPIView.as_view()),

]

urlpatterns = format_suffix_patterns(urlpatterns)
