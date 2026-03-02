from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from rest_framework import serializers

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
        company = self.context["request"].company

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
    service_type = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=ServiceType.objects.all(),
        write_only=True
    )

    service_type_info = serializers.SerializerMethodField(read_only=True)

    total_amount = serializers.DecimalField(max_digits=12, decimal_places=4, write_only=True)
    unit_price_net = serializers.DecimalField(max_digits=12, decimal_places=4, read_only=True)
    vat_percent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = JobLine
        fields = (
            "job",
            "service_type",
            "service_type_info",          
            "quantity",
            "total_amount",
            "unit_price_net",
            "vat_percent",
            "uf",
        )
        read_only_fields = (
            "job",
            "service_type_info",
            "unit_price_net",
            "vat_percent",
            "uf",
        )

    def create(self, validated_data):
        total_amount = validated_data.pop("total_amount")
        quantity = validated_data.get("quantity")
        service_type = validated_data.get("service_type")

        print('3570', service_type)

        vat = service_type.vat_percent

        if quantity and quantity != 0:
            unit_price_net = (total_amount / quantity).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP
            )
        else:
            unit_price_net = Decimal("0.0000")

        return JobLine.objects.create(
            unit_price_net=unit_price_net,
            vat_percent=vat,
            **validated_data
        )

    def get_service_type_info(self, obj):
        return {
            "uf": obj.service_type.uf,
            "name": obj.service_type.name,
            "code": obj.service_type.code,
        }


class JobSerializer(serializers.ModelSerializer):
    customer = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=Contact.objects.all(),
        write_only=True
    )
    point = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=PointOfService.objects.all()
    )

    customer_info = serializers.SerializerMethodField(read_only=True)
    point_info = serializers.SerializerMethodField(read_only=True)
    total_amount = serializers.SerializerMethodField()

    job_lines = JobLineSerializer(many=True)

    class Meta:
        model = Job
        fields = "__all__"
        read_only_fields = ("company", "created_at", "uf", )

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("job_lines", [])
        job = Job.objects.create(**validated_data)

        print('6080', lines_data)
     
        for line_data in lines_data:
            print('6084', line_data)
            serializer = JobLineSerializer(
                    data=line_data,
                    context=self.context
                )
            serializer.is_valid(raise_exception=True)
            serializer.save(job=job)

        return job
       

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("job_lines", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if lines_data is not None:
            instance.job_lines.all().delete()

            for line_data in lines_data:
                serializer = JobLineSerializer(
                    data=line_data,
                    context=self.context
                )
                serializer.is_valid(raise_exception=True)
                serializer.save(job=instance)

        return instance

    def get_customer_info(self, obj):
        return {
            "uf": obj.customer.uf,
            "company_name": obj.customer.company_name,
            "alias_company_name": obj.customer.alias_company_name,
        }

    def get_point_info(self, obj):
        return {
            "uf": obj.point.uf,
            "name": obj.point.name,
            "code": obj.point.code,
            
        }

    def get_total_amount(self, obj):
        return sum(
            line.quantity * line.unit_price
            for line in obj.job_lines.all()
        )


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