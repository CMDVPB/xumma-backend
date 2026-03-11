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

    uf = serializers.CharField(required=False)

    parent_line = serializers.PrimaryKeyRelatedField(
        queryset=JobLine.objects.all(),
        required=False,
        allow_null=True
    )

    service_group = serializers.PrimaryKeyRelatedField(
        queryset=ServiceGroup.objects.all(),
        required=False,
        allow_null=True
    )

    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        write_only=True
    )

    class Meta:
        model = JobLine
        fields = (
            "uf",
            "service_type",
            "service_type_uf",
            "service_group",
            "parent_line",
            "description",
            "quantity",
            "position",
            "total_amount",
            "unit_price_net",
            "vat_percent",
            "other_charges",
        )
        read_only_fields = ("unit_price_net", "vat_percent")

    def validate(self, data):
        parent = data.get("parent_line")
        if parent and parent.parent_line:
            raise serializers.ValidationError(
                "Only one level of additional services allowed."
            )
        return data

    def create(self, validated_data):
        return self._save_line(validated_data)

    def update(self, instance, validated_data):
        return self._save_line(validated_data, instance=instance)

    def _save_line(self, validated_data, instance=None, job=None):
        total_amount = validated_data.pop("total_amount")
        quantity = validated_data.get("quantity")
        service_type = validated_data.get("service_type")

        vat = service_type.vat_percent

        if quantity and quantity != 0:
            unit_price_net = (total_amount / quantity).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        else:
            unit_price_net = Decimal("0.00")

        if instance:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.unit_price_net = unit_price_net
            instance.vat_percent = vat
            instance.save()
            return instance

        return JobLine.objects.create(
            job=job,
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

    customer_info = serializers.SerializerMethodField()
    point_info = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    assigned_to_info = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = "__all__"
        read_only_fields = ("company", "created_at", "uf")

    @transaction.atomic
    def create(self, validated_data):
        job_lines_data = validated_data.pop("job_lines", [])

        request = self.context["request"]
        company = get_user_company(request.user)

        job = Job.objects.create(**validated_data)

        child = self.fields["job_lines"].child

        for line_data in job_lines_data:
            child._save_line(line_data, job=job)

        return job

    @transaction.atomic
    def update(self, instance, validated_data):
        job_lines_data = validated_data.pop("job_lines", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if job_lines_data is None:
            return instance

        child = self.fields["job_lines"].child

        existing_lines = {line.uf: line for line in instance.job_lines.all()}
        incoming_ufs = set()

        for line_data in job_lines_data:
            line_uf = line_data.get("uf")

            if line_uf and line_uf in existing_lines:
                incoming_ufs.add(line_uf)
                child._save_line(
                    line_data,
                    instance=existing_lines[line_uf],
                )
            else:
                new_line = child._save_line(
                    line_data,
                    job=instance,
                )
                incoming_ufs.add(new_line.uf)

        # delete removed lines
        for uf, line in existing_lines.items():
            if uf not in incoming_ufs:
                line.delete()

        return instance

    def get_total_amount(self, obj):
        total = Decimal("0")

        for line in obj.job_lines.all():
            print("LINE DEBUG:", line.total_net, line.other_charges)

            total += line.total_net + (line.other_charges or Decimal("0"))

        return total

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

    def get_assigned_to_info(self, obj):
        if not obj.assigned_to:
            return None

        return {
            "uf": obj.assigned_to.uf,
            "name": obj.assigned_to.get_full_name(),
        }


class ServiceTypeTierSerializer(serializers.ModelSerializer):

    class Meta:
        model = ServiceTypeTier
        fields = ("id", "from_quantity", "to_quantity", "price", "uf",
                  )


class ServiceTypeSerializer(serializers.ModelSerializer):
    pricing_tiers = ServiceTypeTierSerializer(many=True, required=False)

    class Meta:
        model = ServiceType
        fields = "__all__"
        read_only_fields = ("uf", "company")

    def create(self, validated_data):
        tiers_data = validated_data.pop("pricing_tiers", [])

        service = ServiceType.objects.create(**validated_data)

        for tier in tiers_data:
            ServiceTypeTier.objects.create(
                service_type=service,
                **tier
            )

        return service


    @transaction.atomic
    def update(self, instance, validated_data):
        tiers_data = validated_data.pop("pricing_tiers", None)

        # update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # update tiers
        if tiers_data is not None:
            instance.pricing_tiers.all().delete()

            for tier in tiers_data:
                ServiceTypeTier.objects.create(
                    service_type=instance,
                    **tier
                )

        return instance
    

    def validate_pricing_tiers(self, pricing_tiers):

        pricing_tiers = sorted(pricing_tiers, key=lambda x: x["from_quantity"])

        last_end = 0

        for tier in pricing_tiers:

            if tier["from_quantity"] <= last_end:
                raise serializers.ValidationError(
                    "Tier ranges overlap."
                )

            last_end = tier["to_quantity"] or 999999

        return pricing_tiers


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
class BrokerCustomerPricingUpsertSerializer(serializers.Serializer):
    tier_id = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_active = serializers.BooleanField()

###### END BROKER PRICING ######

###### START STAFF ######
class BrokerStaffSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "uf",
            "name",
            "phone",
            "email",
            "role",
        )

    def get_name(self, obj):
        return obj.get_full_name()
    
    def get_phone(self, obj):
        return obj.phone

    def get_role(self, obj):
        if obj.groups.filter(name="level_leader_broker").exists():
            return "leader"
        if obj.groups.filter(name="level_broker").exists():
            return "broker"
        return None


class BrokerBaseSalarySerializer(serializers.ModelSerializer):

    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())
    uf = serializers.CharField(read_only=True)
    
    class Meta:
        model = BrokerBaseSalary
        fields = [
            "id",
            "amount",
            "currency",
            "valid_from",
            "uf",
        ]

    def create(self, validated_data):
        validated_data["company"] = self.context["company"]
        validated_data["user"] = self.context["user"]

        return super().create(validated_data)


class BrokerCommissionSerializer(serializers.ModelSerializer):

    customer = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all())
    uf = serializers.CharField(read_only=True)

    class Meta:
        model = BrokerCommission
        fields = [
            "id",
            "customer",
            "service_type",
            "type",     
            "value",     
            "valid_from",
            "valid_to",
            "uf",
        ]

    def create(self, validated_data):
        validated_data["company"] = self.context["company"]
        validated_data["user"] = self.context["user"]

        return super().create(validated_data)


class BrokerStaffDetailsSerializer(serializers.ModelSerializer):

    broker_base_salaries = BrokerBaseSalarySerializer(many=True)
    broker_commissions = BrokerCommissionSerializer(many=True)
    role = serializers.SerializerMethodField()
   

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "broker_base_salaries",
            "broker_commissions",
            "role",
            "uf",
            
            # Property
            "get_full_name",
        ]   
 

    def get_role(self, obj):
        if obj.groups.filter(name="level_leader_broker").exists():
            return "leader"
        if obj.groups.filter(name="level_broker").exists():
            return "broker"
        return None



class BrokerStaffCompensationSerializer(WritableNestedModelSerializer):

    broker_base_salaries = BrokerBaseSalarySerializer(many=True)
    broker_commissions = BrokerCommissionSerializer(many=True)

    class Meta:
        model = User
        fields = [
            "broker_base_salaries",
            "broker_commissions",
        ]

###### END STAFF ######