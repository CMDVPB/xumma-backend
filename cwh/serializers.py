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
    warehouse_uf = serializers.CharField(max_length=36)
    movement_status = serializers.ChoiceField(
        choices=["expected_warehouse", "arrived_warehouse"],
        required=False,
        default="arrived_warehouse",
    )


class BulkUnloadSerializer(serializers.Serializer):
    load_ufs = serializers.ListField(
        child=serializers.CharField(max_length=36),
        allow_empty=False,
    )
    warehouse_uf = serializers.CharField(max_length=36)
    movement_status = serializers.ChoiceField(
        choices=["expected_warehouse", "arrived_warehouse"],
        required=False,
        default="arrived_warehouse",
    )


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
        fields = ["id", "uf", "value", "label", "serial_number"]


class LoadWarehouseListSerializer(serializers.ModelSerializer):
    country = CountryMiniSerializer(source="country_warehouse", read_only=True)

    loads_count = serializers.IntegerField(read_only=True)
    loads_expected_count = serializers.IntegerField(read_only=True)
    loads_arrived_count = serializers.IntegerField(read_only=True)

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
            "loads_expected_count",
            "loads_arrived_count",
        ]


class LoadWarehouseDetailSerializer(LoadWarehouseListSerializer):
    # same fields, just reuse
    pass


class TripMiniSerializer(serializers.Serializer):
    uf = serializers.CharField(required=False)
    rn = serializers.CharField(required=False, allow_null=True)
    trip_number = serializers.CharField(required=False, allow_null=True)


class WarehouseMiniSerializer(serializers.Serializer):
    uf = serializers.CharField(required=False)
    name_warehouse = serializers.CharField(required=False, allow_null=True)


class VehicleMiniSerializer(serializers.Serializer):
    uf = serializers.CharField(required=False)
    reg_number = serializers.CharField(required=False, allow_null=True)


class WarehouseLoadListSerializer(serializers.ModelSerializer):
    bill_to = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    warehouse = serializers.SerializerMethodField()
    display_location_type = serializers.SerializerMethodField()
    vehicle_tractor = serializers.SerializerMethodField()
    vehicle_trailer = serializers.SerializerMethodField()

    warehouse_arrived_at = serializers.DateTimeField(read_only=True)
    warehouse_current_status = serializers.CharField(read_only=True)

    total_pieces = serializers.IntegerField(read_only=True)
    total_weight = serializers.FloatField(read_only=True)
    total_volume = serializers.FloatField(read_only=True)
    total_ldm = serializers.FloatField(read_only=True)

    class Meta:
        model = Load
        fields = [
            "uf",
            "sn",
            "customer_ref",
            "load_address",
            "unload_address",
            "location_type",
            "display_location_type",
            "warehouse_current_status",
            "warehouse_arrived_at",
            "bill_to",
            "trip",
            "warehouse",
            "vehicle_tractor",
            "vehicle_trailer",
            "total_pieces",
            "total_weight",
            "total_volume",
            "total_ldm",
        ]

    def get_display_location_type(self, obj):
        if getattr(obj, "warehouse_current_status", None) in ["expected_warehouse", "arrived_warehouse"]:
            return "warehouse"
        return obj.location_type
    
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

    def get_vehicle_tractor(self, obj):
            unit = getattr(obj, "vehicle_tractor", None)
            if not unit:
                return None
            return {
                "uf": getattr(unit, "uf", None),
                "reg_number": getattr(unit, "reg_number", None),
            }

    def get_vehicle_trailer(self, obj):
        unit = getattr(obj, "vehicle_trailer", None)
        if not unit:
            return None
        return {
            "uf": getattr(unit, "uf", None),
            "reg_number": getattr(unit, "reg_number", None),
        }

class LoadArriveToWarehouseSerializer(serializers.Serializer):
    warehouse_uf = serializers.CharField(max_length=36)

###### END LOADS IN THE WAREHOUSE ######
