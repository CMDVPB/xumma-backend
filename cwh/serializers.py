from rest_framework import serializers

from app.models import LoadWarehouse


class LoadWarehouseListSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()

    class Meta:
        model = LoadWarehouse
        fields = [
            "id",
            "uf",
            "name_warehouse",
            "address_warehouse",
            "city_warehouse",
            "zip_code_warehouse",
            "country",
            "is_active",
        ]

    def get_country(self, obj):
        if not obj.country_warehouse:
            return None
        return {
            "id": obj.country_warehouse.id,
            "uf": getattr(obj.country_warehouse, "uf", None),
            "code": getattr(obj.country_warehouse, "code", None),
            "label": getattr(obj.country_warehouse, "label", None),
        }


class LoadUnloadSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField()


class BulkUnloadSerializer(serializers.Serializer):
    load_ufs = serializers.ListField(
        child=serializers.CharField(max_length=36),
        allow_empty=False,
    )
    warehouse_id = serializers.IntegerField()


class LoadReloadSerializer(serializers.Serializer):
    trip_id = serializers.IntegerField()
