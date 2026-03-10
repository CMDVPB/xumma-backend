from rest_framework import serializers
from logistic.models import WHLocation


class WHLocationSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = WHLocation
        fields = [
            "uf",
            "code",
            "name",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "uf",
            "created_at",
        ]