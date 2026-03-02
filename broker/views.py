import logging
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from abb.utils import get_user_company
from broker.helpers import get_user_role_in_point
from broker.mixins import CompanyScopedMixin, JobVisibilityQuerysetMixin
from broker.models import CustomerServicePrice, Job, PointMembership, PointOfService, Role, ServiceType

from broker.permissions import IsAdminOrManager, JobAccessPermission
from broker.serializers import (CustomerServicePriceSerializer, 
                                JobSerializer, PointMembershipSerializer, PointOfServiceSerializer, ServiceTypeSerializer)

logger = logging.getLogger(__name__)

User = get_user_model()

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


class PointDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = PointOfServiceSerializer
    lookup_field = "uf"

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
    
   
    def perform_destroy(self, instance):
        if instance.point_memberships.filter(is_active=True).exists():
            raise ValidationError("Cannot delete point with active members.")

        if Job.objects.filter(point=instance).exists():
            raise ValidationError("Cannot delete point with existing jobs.")

        instance.delete()


class PointMembershipListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointMembershipSerializer

    def get_queryset(self):
        point_uf = self.kwargs["uf"]       
        return PointMembership.objects.filter(
            company=self.get_company(),
            point__uf=point_uf,
            is_active=True,
        )

    def perform_create(self, serializer):
        point = PointOfService.objects.get(
            uf=self.kwargs["uf"],
            company=self.get_company()
        )

        if serializer.validated_data["role"] == Role.LEADER:
            if PointMembership.objects.filter(
                company=self.get_company(),
                point=point,
                role=Role.LEADER,
                is_active=True
            ).exists():        
                raise ValidationError("Point already has a leader.")
            
        user = serializer.validated_data["user"]

        if get_user_company(user) != self.get_company():
            raise ValidationError("User not in this company")
        
        serializer.save(
            company=self.get_company(),
            point=point
        )


class PointMembershipDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointMembershipSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return PointMembership.objects.filter(
            company=self.get_company()
        )

    def perform_destroy(self, instance):
        # soft delete
        instance.is_active = False
        instance.save()


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

        serializer.save(company=company, assigned_to=user)


class JobRetrieveUpdateDestroyView(
    CompanyScopedMixin,
    JobVisibilityQuerysetMixin,
    RetrieveUpdateDestroyAPIView
):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, JobAccessPermission]
    lookup_field = 'uf'

    def get_queryset(self):
        qs = (Job.objects
                .filter(company=self.get_company())
                .select_related("point", "customer")
                .prefetch_related("job_lines__service_type"))
        
        return self.filter_queryset_by_visibility(qs)
    
    
class ServiceTypeListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ServiceTypeSerializer

    def get_queryset(self):
        return ServiceType.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


class ServiceTypeDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = ServiceTypeSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return ServiceType.objects.filter(company=self.get_company())


class CustomerServicePriceListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = CustomerServicePriceSerializer

    def get_queryset(self):
        return CustomerServicePrice.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())