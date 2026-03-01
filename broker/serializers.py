from rest_framework import serializers
from .models import *

class PointOfServiceSerializer(serializers.ModelSerializer):
    members_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PointOfService
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at")



class PointMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointMembership
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at")


class TeamVisibilityGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamVisibilityGrant
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at", "created_by")


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = "__all__"
        read_only_fields = ("uf", "company", "created_at")


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