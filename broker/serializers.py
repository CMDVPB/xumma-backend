from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer

from abb.utils import get_user_company
from att.models import Contact
from .models import *

class PointOfServiceSerializer(serializers.ModelSerializer):
    leader = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="uf",
        required=False,
        allow_null=True,
        write_only=True,
    )
    leader_info = serializers.SerializerMethodField(read_only=True)
    leader_uf = serializers.SerializerMethodField()

    members_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PointOfService
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at")

    def get_leader_info(self, obj):
        leader_membership = obj.point_memberships.filter(
            role=Role.LEADER,
            is_active=True
        ).select_related("user").first()

        if not leader_membership:
            return None

        user = leader_membership.user
        return {
            "id": user.id,
            "email": user.email,
            "full_name": getattr(user, "full_name", None),
             "uf": user.uf,
        }
    
    def get_leader_uf(self, obj):
        membership = obj.point_memberships.filter(
            role=Role.LEADER,
            is_active=True
        ).select_related("user").first()

        return membership.user.uf if membership else None

    @transaction.atomic
    def create(self, validated_data):
        leader = validated_data.pop("leader", None)
        request = self.context["request"]
        company = get_user_company(request.user)

        point = PointOfService.objects.create(
            company=company,
            **validated_data
        )

        if leader:
            PointMembership.objects.create(
                company=company,
                point=point,
                user=leader,
                role=Role.LEADER
            )

        return point

    @transaction.atomic
    def update(self, instance, validated_data):
        leader = validated_data.pop("leader", None)

        # Update point fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # If leader not provided in PATCH -> don't touch leader
        if leader is None:
            return instance

        company = instance.company

        # 1) Deactivate current active leader(s) EXCEPT the new leader
        instance.point_memberships.filter(
            role=Role.LEADER,
            is_active=True,
        ).exclude(user=leader).update(is_active=False)

        # 2) Ensure the new leader has an ACTIVE membership for this point
        #    If membership already exists (broker/leader/inactive), update it
        membership, created = PointMembership.objects.get_or_create(
            company=company,
            point=instance,
            user=leader,
            defaults={"role": Role.LEADER, "is_active": True},
        )

        if not created:
            # Re-activate and set role to LEADER
            if membership.role != Role.LEADER or not membership.is_active:
                membership.role = Role.LEADER
                membership.is_active = True
                membership.save(update_fields=["role", "is_active"])

        return instance


class PointMembershipSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=User.objects.all()
    )

    point = serializers.SlugRelatedField(
        slug_field="uf",
        read_only=True
    )


    user_full_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)


    class Meta:
        model = PointMembership
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at", "point")

    def get_user_full_name(self, obj):
        return getattr(obj.user, "full_name", None) or obj.user.email
    

class TeamVisibilityGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamVisibilityGrant
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at", "created_by")


class JobLineSerializer(serializers.ModelSerializer):
    service_type_uf = serializers.CharField(
        source="service_type.uf",
        read_only=True
    )

    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        write_only=True
    )

    class Meta:
        model = JobLine
        fields = (
            "id",
            "service_type",
            "description",
            "quantity",
            "total_amount",      # write only
            "unit_price_net",    # read only
            "vat_percent",
            "service_type_uf",
            "uf",
        )
        read_only_fields = ("unit_price_net", "vat_percent")


    def create(self, validated_data):
        return self._save_line(validated_data)

    def update(self, instance, validated_data):
        return self._save_line(validated_data, instance)

    def _save_line(self, validated_data, instance=None):
        total_amount = validated_data.pop("total_amount")
        quantity = validated_data.get("quantity")
        service_type = validated_data.get("service_type")

        vat = service_type.vat_percent

        if quantity and quantity != 0:
            unit_price_net = (total_amount / quantity).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP
            )
        else:
            unit_price_net = Decimal("0.0000")

        if instance:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.unit_price_net = unit_price_net
            instance.vat_percent = vat
            instance.save()
            return instance

        return JobLine.objects.create(
            unit_price_net=unit_price_net,
            vat_percent=vat,
            **validated_data
        )


class JobSerializer(WritableNestedModelSerializer):

    customer = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=Contact.objects.all(),
        write_only=True
    )

    point = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=PointOfService.objects.all(),
        write_only=True
    )

    job_lines = JobLineSerializer(many=True)

    # READ ONLY FIELDS
    customer_info = serializers.SerializerMethodField()
    point_info = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    assigned_to_info = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = "__all__"
        read_only_fields = ("company", "created_at", "uf",)


    def get_customer_info(self, obj):
        if not obj.customer:
            return None

        return {
            "uf": obj.customer.uf,
            "company_name": obj.customer.company_name,
            "alias_company_name": obj.customer.alias_company_name,
        }

    def get_point_info(self, obj):
        if not obj.point:
            return None

        return {
            "uf": obj.point.uf,
            "name": obj.point.name,
            "code": obj.point.code,
        }

    def get_total_amount(self, obj):
        return sum(
            line.quantity * line.unit_price_net
            for line in obj.job_lines.all()
        )
    
    def get_assigned_to_info(self, obj):
        if not obj.assigned_to:
            return None

        return {
            "uf": obj.assigned_to.uf,
            "name": obj.assigned_to.get_full_name(),
        }


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = "__all__"
        read_only_fields = ("uf", "company")

    
class CustomerServicePriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerServicePrice
        fields = "__all__"
        read_only_fields = ("uf", "company")


###### START BROKER REPORTS ######
class RevenueByCustomerSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=18, decimal_places=2)


class RevenueByPointSerializer(serializers.Serializer):
    point_id = serializers.IntegerField()
    point_name = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=18, decimal_places=2)


class JobsByPointSerializer(serializers.Serializer):
    point_id = serializers.IntegerField()
    point_name = serializers.CharField()
    total_jobs = serializers.IntegerField()


class BrokerReportsOverviewSerializer(serializers.Serializer):
    top_customers = RevenueByCustomerSerializer(many=True)
    revenue_by_point = RevenueByPointSerializer(many=True)
    jobs_by_point = JobsByPointSerializer(many=True)


class BrokerEmployeePerformanceItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    name = serializers.CharField()
    jobs = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=18, decimal_places=2)


class BrokerEmployeePerformanceSerializer(serializers.Serializer):
    days_30 = BrokerEmployeePerformanceItemSerializer(many=True)
    days_90 = BrokerEmployeePerformanceItemSerializer(many=True)
    days_180 = BrokerEmployeePerformanceItemSerializer(many=True)

###### END BROKER REPORTS ######

###### START BROKER PRICING ######

class BrokerCustomerPricingSerializer(serializers.Serializer):
    service_type_id = serializers.IntegerField()
    service_name = serializers.CharField()
    default_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    special_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    is_active = serializers.BooleanField()


class BrokerCustomerPricingUpsertSerializer(serializers.Serializer):
    service_type_id = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_active = serializers.BooleanField()

###### END BROKER PRICING ######