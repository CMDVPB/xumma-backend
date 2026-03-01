from django.db.models import Count, Q
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from broker.helpers import get_user_role_in_point, visible_points
from broker.mixins import CompanyScopedMixin, JobVisibilityQuerysetMixin
from broker.models import CustomerServicePrice, Job, PointMembership, PointOfService, ServiceType

from broker.permissions import JobAccessPermission
from broker.serializers import (CustomerServicePriceSerializer, 
                                JobSerializer, PointMembershipSerializer, PointOfServiceSerializer, ServiceTypeSerializer)

class PointListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointOfServiceSerializer

    def get_queryset(self):
            return (
                PointOfService.objects
                .filter(company=self.get_company())
                .annotate(
                    members_count=Count(
                        "point_memberships",
                        filter=Q(point_memberships__is_active=True),
                        distinct=True
                    )
                )
            )

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


class MembershipListCreateView(CompanyScopedMixin, ListCreateAPIView):
    serializer_class = PointMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PointMembership.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


class JobListCreateView(CompanyScopedMixin, JobVisibilityQuerysetMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, JobAccessPermission]
    serializer_class = JobSerializer

    def get_queryset(self):
        qs = Job.objects.select_related(
            "point",
            "customer",
            "assigned_to"
        ).filter(company=self.get_company())

        return self.filter_queryset_by_visibility(qs)

    def perform_create(self, serializer):
        company = self.get_company()
        user = self.request.user

        point = serializer.validated_data["point"]

        # Admin override
        if user.groups.filter(name="level_admin").exists():
            serializer.save(company=company)
            return

        role = get_user_role_in_point(user, company, point)

        if not role:
            raise PermissionDenied("You are not a member of this team")

        serializer.save(company=company)


class JobRetrieveUpdateDestroyView(
    CompanyScopedMixin,
    RetrieveUpdateDestroyAPIView
):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, JobAccessPermission]

    def get_queryset(self):
        return Job.objects.filter(company=self.get_company())
    
    
class ServiceTypeListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ServiceTypeSerializer

    def get_queryset(self):
        return ServiceType.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


class ServiceTypeDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ServiceTypeSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return ServiceType.objects.filter(company=self.get_company())


class CustomerServicePriceListCreateView(CompanyScopedMixin, ListCreateAPIView):
    serializer_class = CustomerServicePriceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CustomerServicePrice.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())