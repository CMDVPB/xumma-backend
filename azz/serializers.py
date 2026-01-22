
from abb.utils import get_user_company
from att.models import Contact
from .models import FuelTank, TruckFueling, Vehicle
from .models import FuelTank, TankRefill
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers
from .models import ImportBatch, ImportRow


class ImportCreateSerializer(serializers.Serializer):
    supplier_uf = serializers.CharField()
    period_from = serializers.DateField()
    period_to = serializers.DateField()

    def validate(self, data):
        if data["period_from"] > data["period_to"]:
            raise serializers.ValidationError("Invalid period range")
        return data


class ImportBatchListSerializer(serializers.ModelSerializer):
    supplier_company_name = serializers.CharField(
        source="supplier.company_name", read_only=True)

    class Meta:
        model = ImportBatch
        fields = (
            "supplier_company_name",
            'year',
            'sequence',
            "period_from",
            "period_to",
            "status",
            "created_at",
            "finished_at",
            "totals",
            "uf",
        )


class ImportRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRow
        fields = (
            "row_number",
            "status",
            "error_message",
            "matched_trip_id",
            "raw_data",
        )


class ImportBatchDetailSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.company_name", read_only=True)
    rows = ImportRowSerializer(many=True, read_only=True)

    class Meta:
        model = ImportBatch
        fields = "__all__"


###### Start Fuel & AdBlue ######

class FuelTankSerializer(serializers.ModelSerializer):
    current_stock_l = serializers.SerializerMethodField()

    class Meta:
        model = FuelTank
        fields = (
            "fuel_type",
            "capacity_l",
            "current_stock_l",
            "uf",
        )

    def get_current_stock_l(self, obj):
        return obj.get_current_fuel_stock()


class TankRefillCreateSerializer(serializers.ModelSerializer):
    tank_uf = serializers.CharField(write_only=True)

    class Meta:
        model = TankRefill
        fields = (
            "tank_uf",
            "supplier",
            "vehicle",
            "person",
            "date",
            "quantity_l",
            "actual_quantity_l",
            "price_l",
            "comments",
        )

    def validate(self, attrs):
        # basic checks (non-negative)
        for f in ("quantity_l", "actual_quantity_l", "price_l"):
            if attrs.get(f) is not None and attrs[f] < Decimal("0"):
                raise serializers.ValidationError({f: "Must be >= 0"})

        if not attrs.get("date"):
            attrs["date"] = timezone.now()

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user_company = get_user_company(request.user)
        company = user_company

        tank_uf = validated_data.pop("tank_uf")

        with transaction.atomic():
            # Lock the tank row
            tank = (
                FuelTank.objects.select_for_update()
                .select_related("company")
                .get(uf=tank_uf, company=company)
            )

            # Calculate stock inside transaction
            current = tank.get_current_fuel_stock(using_actual=True)
            incoming = validated_data["actual_quantity_l"]

            if current + incoming > tank.capacity_l:
                raise serializers.ValidationError(
                    {"actual_quantity_l": "Tank capacity exceeded"}
                )

            refill = TankRefill.objects.create(tank=tank, **validated_data)
            return refill


class TankRefillUpdateSerializer(serializers.ModelSerializer):
    supplier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(),  write_only=True)

    class Meta:
        model = TankRefill
        fields = (
            "supplier",
            "vehicle",
            "person",
            "date",
            "quantity_l",
            "actual_quantity_l",
            "price_l",
            "comments",
            "uf",
        )


class TruckFuelingCreateSerializer(serializers.ModelSerializer):
    tank_uf = serializers.CharField(write_only=True)
    vehicle_uf = serializers.CharField(write_only=True)

    class Meta:
        model = TruckFueling
        fields = (
            "tank_uf",
            "vehicle_uf",
            "quantity_l",
            "fueled_at",
            "driver",
        )

    def validate(self, attrs):
        if attrs.get("quantity_l") is None or attrs["quantity_l"] <= Decimal("0"):
            raise serializers.ValidationError({"quantity_l": "Must be > 0"})

        if not attrs.get("fueled_at"):
            attrs["fueled_at"] = timezone.now()

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user_company = get_user_company(request.user)
        company = user_company

        tank_uf = validated_data.pop("tank_uf")
        vehicle_uf = validated_data.pop("vehicle_uf")

        # If driver not provided, default to current user
        validated_data.setdefault("driver", request.user)

        with transaction.atomic():
            # Lock tank row to prevent concurrent stock changes
            tank = (
                FuelTank.objects.select_for_update()
                .select_related("company")
                .get(uf=tank_uf, company=company)
            )

            # Ensure vehicle belongs to same company (adjust field name if needed)
            vehicle = Vehicle.objects.get(uf=vehicle_uf, company=company)

            current = tank.get_current_fuel_stock(using_actual=True)
            outgoing = validated_data["quantity_l"]

            if outgoing > current:
                raise serializers.ValidationError(
                    {"quantity_l": "Not enough fuel in tank"})

            fueling = TruckFueling.objects.create(
                tank=tank,
                vehicle=vehicle,
                **validated_data
            )
            return fueling


class TankRefillListSerializer(serializers.ModelSerializer):
    tank = serializers.SerializerMethodField()
    supplier = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    person = serializers.SerializerMethodField()

    class Meta:
        model = TankRefill
        fields = (
            "uf",
            "date",
            "quantity_l",
            "actual_quantity_l",
            "price_l",
            "comments",
            "tank",
            "supplier",
            "vehicle",
            "person",
        )

    def _simple_obj(self, obj, label_field="name"):
        if not obj:
            return None
        return {
            "id": obj.id,
            "uf": getattr(obj, "uf", None),
            "company_name": getattr(obj, label_field, str(obj)),
        }

    def get_tank(self, obj):
        return {
            "uf": obj.tank.uf,
            "fuel_type": obj.tank.fuel_type,
            "capacity_l": obj.tank.capacity_l,
        }

    def get_supplier(self, obj):
        # Contact model – adapt label field if needed
        return self._simple_obj(obj.supplier, "name")

    def get_vehicle(self, obj):
        # VehicleUnit model – adapt label field if needed
        return self._simple_obj(obj.vehicle, "registration_number")

    def get_person(self, obj):
        # Person model – adapt label field if needed
        return self._simple_obj(obj.person, "full_name")
###### End Fuel & AdBlue ######
