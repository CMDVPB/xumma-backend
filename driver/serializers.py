from rest_framework import serializers
from django.conf import settings

from abb.models import Country, Currency
from app.models import TypeCost
from att.models import Vehicle
from axx.models import Load, LoadEvidence, Trip
from ayy.models import ItemCost, ItemForItemCost
from driver.utils import format_site
from .models import DriverLocation


class DriverLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLocation
        fields = ("lat", "lng", "speed", "heading")


class ActiveTripSerializer(serializers.ModelSerializer):

    tractor_number = serializers.CharField(
        source='vehicle_tractor.reg_number', allow_null=True
    )

    trailer_number = serializers.CharField(
        source='vehicle_trailer.reg_number', allow_null=True
    )

    drivers = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = (
            'id',
            'rn',
            'tractor_number',
            'trailer_number',
            'drivers',
            'location',
            'uf',
        )

    def get_drivers(self, obj):
        result = []

        for driver in obj.drivers.all():

            loc = getattr(driver, 'driver_location', None)

            result.append({
                'id': driver.id,
                'name': driver.get_full_name(),
                'uf': driver.uf,
                'location': {
                    'lat': loc.lat,
                    'lng': loc.lng,
                    'speed': loc.speed,
                    'heading': loc.heading,
                    'updated_at': loc.updated_at,
                } if loc else None
            })

        return result

    def get_location(self, obj):
        """
        Strategy used by real fleet systems:

        → Use first driver with telemetry
        → Avoid assumptions about tractor device
        """

        driver = obj.drivers.first()
        if not driver:
            return None

        loc = getattr(driver, 'driverlocation', None)
        if not loc:
            return None

        return {
            'lat': loc.lat,
            'lng': loc.lng,
            'speed': loc.speed,
            'heading': loc.heading,
            'updated_at': loc.updated_at,
        }


###### START DRIVER LOADING ######

class ConfirmLoadingSerializer(serializers.Serializer):
    uf = serializers.CharField()


class LoadEvidenceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LoadEvidence
        fields = [
            "id",
            "type",
            "image",
            "image_url",
            "created_at",
            'uf'
        ]

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError("Image is required")

        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image too large")

        return value

    def get_image_url(self, obj):
        return f"{settings.MOBILE_BACKEND_URL}/api/load-evidences/{obj.uf}/"


class DriverLoadSerializer(serializers.ModelSerializer):
    load_evidences = LoadEvidenceSerializer(many=True, read_only=True)

    load_address = serializers.SerializerMethodField()
    unload_address = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "sn",
            "driver_status",
            "uf",

            "load_address",
            "unload_address",
            "reference",

            "load_evidences",
        ]

    def get_load_address(self, obj):
        entry = (
            obj.entry_loads
            .filter(action="loading")
            .order_by("order", "id")
            .select_related("shipper")
            .first()
        )

        return format_site(entry.shipper) if entry else None

    def get_unload_address(self, obj):
        entry = (
            obj.entry_loads
            .filter(action="unloading")
            .order_by("order", "id")
            .select_related("shipper")
            .first()
        )

        return format_site(entry.shipper) if entry else None

    def get_reference(self, obj):
        entry = (
            obj.entry_loads
            .filter(action="loading")
            .order_by("order", "id")
            .first()
        )

        return entry.shipperinstructions1 if entry else None


class DriverVehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "reg_number",
            "uf",
        ]


class DriverTripSerializer(serializers.ModelSerializer):
    loads = serializers.SerializerMethodField()

    vehicle_tractor = DriverVehicleSerializer(read_only=True)
    vehicle_trailer = DriverVehicleSerializer(read_only=True)

    class Meta:
        model = Trip
        fields = [
            "rn",
            "date_order",
            "vehicle_tractor",
            "vehicle_trailer",
            "loads",
            "uf",

            "departure_inspection_completed",
        ]

    def get_loads(self, obj):
        loads = obj.trip_loads.all().order_by("date_order")
        return DriverLoadSerializer(loads, many=True).data


###### END DRIVER LOADING ######


###### START DRIVER COSTS DURING TRIP ######

class ItemForItemCostDriverSerializer(serializers.ModelSerializer):

    class Meta:
        model = ItemForItemCost
        fields = [
            "description",
            "code",
            "vat",
            "is_system",
            "uf",
        ]


class ItemCostDriverSerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=Currency.objects.all()
    )

    country = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=Country.objects.all()
    )

    type = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=TypeCost.objects.all()
    )

    item_for_item_cost = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=ItemForItemCost.objects.all(),
        allow_null=True,
        required=False
    )

    type_label = serializers.CharField(source="type.label", read_only=True)
    currency_code = serializers.CharField(
        source="currency.currency_code", read_only=True)
    country_label = serializers.CharField(
        source="country.label", read_only=True)
    item_label = serializers.CharField(
        source="item_for_item_cost.description", read_only=True)

    total = serializers.FloatField(read_only=True)

    receipt_file = serializers.SerializerMethodField()  # read
    receipt_file_upload = serializers.ImageField(
        write_only=True, required=False)  # write

    total_input = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = ItemCost
        fields = [
            "trip",
            "date",
            "type",
            "type_label",
            "country",
            "country_label",
            "quantity",
            "amount",
            'total_input',

            "vat",
            "discount",
            "item_for_item_cost",
            "item_label",
            "currency",
            "currency_code",
            "created_by",
            "total",
            "uf",

            "receipt_file",
            "receipt_file_upload"
        ]
        read_only_fields = ["uf", "created_by", "total"]

    def validate(self, attrs):
        total_input = attrs.pop("total_input", None)

        qty = attrs.get("quantity") or 1
        vat = attrs.get("vat") or 0

        if total_input is not None:

            if total_input < 0:
                raise serializers.ValidationError(
                    {"total_input": "Must be >= 0"})

            divisor = (1 + vat / 100)

            if divisor <= 0:
                raise serializers.ValidationError({"vat": "Invalid VAT value"})

            base_amount = total_input / qty / divisor

            attrs["amount"] = round(base_amount, 4)

        amt = attrs.get("amount")
        if amt is not None and amt < 0:
            raise serializers.ValidationError({"amount": "Must be >= 0"})

        if vat < 0 or vat > 100:
            raise serializers.ValidationError({"vat": "Must be 0..100"})

        return attrs

    def get_receipt_file(self, obj):
        return f"{settings.BACKEND_URL}/api/cost-receipt-files/{obj.uf}/"


class TypeCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeCost
        fields = [
            "uf",
            "label",
            "code",
            "serial_number",
            "is_system",
        ]

###### EMD DRIVER COSTS DURING TRIP ######
