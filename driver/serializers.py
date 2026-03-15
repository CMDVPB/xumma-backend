from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.conf import settings
from rest_framework import serializers

from abb.models import Country, Currency
from app.models import TypeCost
from att.models import Vehicle
from axx.models import Load, LoadEvidence, Trip
from ayy.models import ItemCost, ItemForItemCost
from driver.utils import format_site
from .models import DriverLocation, TripStop, TripStopMessage



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


class DriverLoadCacheSerializer(serializers.ModelSerializer):
    load_evidences = LoadEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Load
        fields = ["uf", "sn", "load_evidences"]


class DriverLoadSerializer(serializers.ModelSerializer):
    load_evidences = LoadEvidenceSerializer(many=True, read_only=True)

    load_address = serializers.SerializerMethodField()
    unload_address = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "sn",
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

            "km_start_driver",
            "km_start_driver_recorded_at",
            "km_end_driver",
            "km_end_driver_recorded_at",
        ]

    def get_loads(self, obj):
        loads = obj.trip_loads.all().order_by("date_order")
        return DriverLoadSerializer(loads, many=True).data


class DriverTripStopSerializer(serializers.ModelSerializer):
    load_sn = serializers.CharField(source="load.sn", read_only=True)
    # optional: entry window if exists
    time_load_min = serializers.DateTimeField(
        source="entry.time_load_min", read_only=True)
    time_load_max = serializers.DateTimeField(
        source="entry.time_load_max", read_only=True)

    unread_count = serializers.IntegerField(read_only=True)

    address_label = serializers.SerializerMethodField()
    address_site = serializers.SerializerMethodField()
    city_site = serializers.SerializerMethodField()
    zip_code_site = serializers.SerializerMethodField()
    country_site = serializers.SerializerMethodField()
    site_name = serializers.SerializerMethodField()
    site_lat = serializers.SerializerMethodField()
    site_lon = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    loading_point_note = serializers.SerializerMethodField()

    pieces_total = serializers.SerializerMethodField()
    weight_total = serializers.SerializerMethodField()
    ldm_total = serializers.SerializerMethodField()
    volume_total = serializers.SerializerMethodField()
    dims_summary = serializers.SerializerMethodField()
    colli_type_summary = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = [
            "uf",
            "order",
            "type",
            "title",           
            "is_completed",
            "date_completed",
            "status",
            "km",

            "load_sn",
            "time_load_min",
            "time_load_max",

            "is_visible_to_driver",

            "unread_count",

            "address_label",
            "address_site",
            "city_site",
            "zip_code_site",
            "country_site",
            "site_name",
            "site_lat",
            "site_lon",
            "reference",
            "loading_point_note",

            "pieces_total",
            "weight_total",
            "ldm_total",
            "volume_total",
            "dims_summary",
            "colli_type_summary",
        ]
        read_only_fields = fields

    def _get_shipper(self, obj):
            entry = getattr(obj, "entry", None)
            # print('6060', obj)
            if not entry:
                return None
            return getattr(entry, "shipper", None)

    def _get_details(self, obj):
            entry = getattr(obj, "entry", None)
            if not entry:
                return []
            return list(entry.entry_details.all())

    def _sum_decimal_field(self, details, field_name):
        total = Decimal("0")
        found = False

        for d in details:
            raw = getattr(d, field_name, None)
            if raw in [None, ""]:
                continue
            try:
                total += Decimal(str(raw).replace(",", "."))
                found = True
            except (InvalidOperation, TypeError, ValueError):
                continue

        if not found:
            return None

        return total

    def get_site_name(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.name_site if shipper else None

    def get_address_site(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.address_site if shipper else None

    def get_city_site(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.city_site if shipper else None

    def get_zip_code_site(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.zip_code_site if shipper else None

    def get_country_site(self, obj):
        shipper = self._get_shipper(obj)
        if not shipper or not shipper.country_code_site:
            return None
        return getattr(shipper.country_code_site, "label", None) or str(shipper.country_code_site)
    
    def get_site_lat(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.lat if shipper else None

    def get_site_lon(self, obj):
        shipper = self._get_shipper(obj)
        return shipper.lon if shipper else None

    def get_address_label(self, obj):
        shipper = self._get_shipper(obj)
        if not shipper:
            return None

        parts = [
            getattr(shipper.country_code_site, "label", None) if shipper.country_code_site else None,
            shipper.zip_code_site,
            shipper.city_site,
            shipper.address_site,
        ]
        return ", ".join([p for p in parts if p]) or None
    
    def get_reference(self, obj):
        shipper = self._get_shipper(obj)
        return getattr(shipper, "instructions1", None) if shipper else None

    def get_loading_point_note(self, obj):
        shipper = self._get_shipper(obj)
        return getattr(shipper, "comment2", None) if shipper else None
    
    def get_pieces_total(self, obj):
        total = self._sum_decimal_field(self._get_details(obj), "pieces")
        if total is None:
            return None

        return str(int(total))

    def get_ldm_total(self, obj):
        total = self._sum_decimal_field(self._get_details(obj), "ldm")
        if total is None:
            return None

        if total <= Decimal("0.01"):
            return None

        return str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def get_weight_total(self, obj):
        total = self._sum_decimal_field(self._get_details(obj), "weight")
        if total is None:
            return None

        return str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def get_volume_total(self, obj):
        total = self._sum_decimal_field(self._get_details(obj), "volume")
        if total is None:
            return None

        return str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def get_dims_summary(self, obj):
        details = self._get_details(obj)
        dims = [d.dims.strip() for d in details if d.dims and d.dims.strip()]
        return " | ".join(dict.fromkeys(dims)) if dims else None

    def get_colli_type_summary(self, obj):
        details = self._get_details(obj)

        counts = {}
        for d in details:
            colli = getattr(d, "colli_type", None)
            if not colli:
                continue

            label = colli.label or colli.code or str(colli)
            raw_pieces = getattr(d, "pieces", None)

            qty = Decimal("0")
            try:
                if raw_pieces not in [None, ""]:
                    qty = Decimal(str(raw_pieces).replace(",", "."))
            except (InvalidOperation, TypeError, ValueError):
                qty = Decimal("0")

            counts[label] = counts.get(label, Decimal("0")) + qty

        if not counts:
            return None

        parts = []
        for label, qty in counts.items():
            qty_str = str(qty.normalize()) if qty != 0 else "0"
            parts.append(f"{qty_str} {label}")

        return " | ".join(parts)


class DriverCompleteTripStopSerializer(serializers.Serializer):
    km = serializers.IntegerField(required=False, min_value=0)
   

class DriverTripKmSerializer(serializers.Serializer):
    km_start_driver = serializers.CharField(required=False, allow_blank=False, max_length=20)
    km_end_driver = serializers.CharField(required=False, allow_blank=False, max_length=20)

    def validate(self, attrs):
        km_start_driver = attrs.get("km_start_driver")
        km_end_driver = attrs.get("km_end_driver")

        if not km_start_driver and not km_end_driver:
            raise serializers.ValidationError(
                "Provide either km_start_driver or km_end_driver."
            )

        if km_start_driver and km_end_driver:
            raise serializers.ValidationError(
                "Provide only one of km_start_driver or km_end_driver."
            )

        return attrs

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


###### START TRIP STOPS ######
class TripStopSerializer(serializers.ModelSerializer):

    load_sn = serializers.CharField(source="load.sn", read_only=True)
    time_load_min = serializers.DateTimeField(
        source="entry.time_load_min", read_only=True)
    time_load_max = serializers.DateTimeField(
        source="entry.time_load_max", read_only=True)

    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = [
            "order",
            "type",
            "title",           
            "is_visible_to_driver",
            "date_completed",
            "status",

            # derived helpers
            "load_sn",
            "time_load_min",
            "time_load_max",

            "unread_count",

            "uf",
        ]

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            # WS / background serialization → cannot compute per-user unread count safely
            return None

        user = request.user

        group_names = getattr(user, "_group_names_cache", None)
        if group_names is None:
            group_names = set(user.groups.values_list("name", flat=True))
            user._group_names_cache = group_names

        if "level_driver" in group_names:
            return TripStopMessage.objects.filter(
                trip_stop=obj,
                is_read_by_driver=False,
            ).exclude(sender__groups__name="level_driver").count()

        return TripStopMessage.objects.filter(
            trip_stop=obj,
            is_read_by_dispatcher=False,
        ).exclude(sender__groups__name="level_dispatcher").count()


class TripStopReorderSerializer(serializers.Serializer):
    orderedUfs = serializers.ListField(
        child=serializers.CharField()
    )


class TripStopVisibilitySerializer(serializers.ModelSerializer):

    class Meta:
        model = TripStop
        fields = ["is_visible_to_driver"]

    def validate(self, attrs):
        stop = self.instance

        if stop.is_completed and attrs.get("is_visible_to_driver") is False:
            raise serializers.ValidationError(
                "Completed stops cannot be hidden from driver"
            )

        return attrs


class TripStopMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source="sender.get_full_name", read_only=True)
    trip_stop_uf = serializers.CharField(source="trip_stop.uf", read_only=True)

    class Meta:
        model = TripStopMessage
        fields = [
            "uf",
            "type",
            "message",
            "created_at",
            "sender",
            "sender_name",
            "is_read_by_driver",
            "is_read_by_dispatcher",

            "trip_stop_uf",
        ]
        read_only_fields = [
            "uf",
            "created_at",
            "sender",
            "is_read_by_driver",
            "is_read_by_dispatcher",
        ]


class TripStopAssignGpsSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lon = serializers.FloatField()

###### END TRIP STOPS ######
