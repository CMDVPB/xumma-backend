from __future__ import annotations

from django.db.models import Avg, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, filters
from django.shortcuts import get_object_or_404

from abb.utils import get_user_company

from .models import POI, POIReview, POIStatus
from .serializers import POIReviewSerializer, POISerializer
from .filters import POIFilter


class POIListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = POISerializer

    filter_backends = [DjangoFilterBackend,
                       filters.OrderingFilter, filters.SearchFilter]
    filterset_class = POIFilter

    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]

    search_fields = ["name", "address_text", "notes"]

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)

        qs = (
            POI.objects
            .filter(company=user_company, status__in=[POIStatus.ACTIVE, POIStatus.PENDING])
            .select_related("created_by", "verified_by")
            .annotate(
                avg_rating=Avg(
                    "poi_reviews__rating_overall",
                    filter=Q(poi_reviews__status_visible=True)
                ),
                reviews_count=Count(
                    "poi_reviews",
                    filter=Q(poi_reviews__status_visible=True)
                ),
            )
        )

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class POIRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = POISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)

        return (
            POI.objects
            .filter(company=user_company, status__in=[POIStatus.ACTIVE, POIStatus.PENDING])
            .select_related("created_by", "verified_by")
            .annotate(
                avg_rating=Avg(
                    "poi_reviews__rating_overall",
                    filter=Q(poi_reviews__status_visible=True)
                ),
                reviews_count=Count(
                    "poi_reviews",
                    filter=Q(poi_reviews__status_visible=True)
                ),
            )
        )


class POIReviewListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = POIReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        poi_id = self.kwargs["poi_id"]

        return POIReview.objects.filter(
            poi_id=poi_id,
            status_visible=True,
        ).select_related("author")

    def perform_create(self, serializer):
        poi_id = self.kwargs["poi_id"]

        poi = get_object_or_404(POI, id=poi_id)

        serializer.save(
            poi=poi,
            author=self.request.user,
        )
