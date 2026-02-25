from rest_framework import serializers

from abb.models import Country
from app.models import LoadWarehouse
from axx.models import Load


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
            "value": getattr(obj.country_warehouse, "value", None),
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


class LoadWarehouseCreateSerializer(serializers.ModelSerializer):
    country_warehouse = serializers.SlugRelatedField(
        queryset=Country.objects.all(),
        slug_field="label"
    )

    class Meta:
        model = LoadWarehouse
        fields = [
            "name_warehouse",
            "address_warehouse",
            "city_warehouse",
            "zip_code_warehouse",
            "country_warehouse",
            "is_active",
        ]

###### START LOADS IN THE WAREHOUSE ######


class CountryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "uf", "code", "label"]


class LoadWarehouseListSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    loads_count = serializers.IntegerField(read_only=True)

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
            "loads_count",
        ]

    def get_country(self, obj):
        if not obj.country_warehouse:
            return None

        return {
            "id": obj.country_warehouse.id,
            "uf": getattr(obj.country_warehouse, "uf", None),
            "value": getattr(obj.country_warehouse, "value", None),
            "label": getattr(obj.country_warehouse, "label", None),
        }


class LoadWarehouseDetailSerializer(LoadWarehouseListSerializer):
    # same fields, just reuse
    pass


# class PartnerMiniSerializer(serializers.Serializer):
#     # matches your frontend usage: bill_to.company_name + status dot usage
#     uf = serializers.CharField(required=False)
#     company_name = serializers.CharField(required=False, allow_null=True)
#     status = serializers.CharField(
#         source="status.name", required=False, allow_null=True)


class TripMiniSerializer(serializers.Serializer):
    uf = serializers.CharField(required=False)
    rn = serializers.CharField(required=False, allow_null=True)
    trip_number = serializers.CharField(required=False, allow_null=True)


class WarehouseMiniSerializer(serializers.Serializer):
    uf = serializers.CharField(required=False)
    name_warehouse = serializers.CharField(required=False, allow_null=True)


class WarehouseLoadListSerializer(serializers.ModelSerializer):
    bill_to = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    warehouse = serializers.SerializerMethodField()

    # annotated in queryset (last movement to this warehouse)
    warehouse_arrived_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Load
        fields = [
            "uf",
            "sn",
            "customer_ref",
            "load_address",
            "unload_address",
            "location_type",
            "warehouse_arrived_at",
            "bill_to",
            "trip",
            "warehouse",
        ]

    def get_bill_to(self, obj):
        bt = obj.bill_to
        if not bt:
            return None

        status = bt.status

        return {
            "uf": bt.uf,
            "company_name": bt.company_name,
            "status": status.name if status else None,
        }

    def get_trip(self, obj):
        trip = getattr(obj, "trip", None)
        if not trip:
            return None
        return {
            "uf": getattr(trip, "uf", None),
            "rn": getattr(trip, "rn", None),
            "trip_number": getattr(trip, "trip_number", None),
        }

    def get_warehouse(self, obj):
        wh = getattr(obj, "warehouse", None)
        if not wh:
            return None
        return {
            "uf": getattr(wh, "uf", None),
            "name_warehouse": getattr(wh, "name_warehouse", None),
        }

###### END LOADS IN THE WAREHOUSE ######
