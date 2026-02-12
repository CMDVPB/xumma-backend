from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers

from abb.models import Currency
from abb.utils import get_user_company
from auu.models import PaymentMethod
from axx.models import LoadInv, Trip, TripAdvancePayment, TripAdvancePaymentStatus

User = get_user_model()


class TripAdvancePaymentListSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_by_label = serializers.SerializerMethodField()

    class Meta:
        model = TripAdvancePayment
        fields = (
            'uf',
            'amount',
            'currency',
            'payment_method',
            'status',
            'purpose',
            'requested_at',
            'approved_at',
            'paid_at',
            'created_by_label',
        )

    def get_currency(self, obj):
        return {
            'currency_code': obj.currency.currency_code
        } if obj.currency else None

    def get_payment_method(self, obj):
        return {
            'code': obj.payment_method.code,
            'name': obj.payment_method.label,
        }

    def get_status(self, obj):
        return {
            'code': obj.status.code,
            'name': obj.status.name,
        }

    def get_created_by_label(self, obj):
        user = obj.created_by
        return user.get_full_name() or user.email


class TripAdvancePaymentCreateSerializer(serializers.ModelSerializer):
    tripUf = serializers.CharField(write_only=True)
    driverUf = serializers.CharField(write_only=True)
    paymentMethodCode = serializers.CharField(write_only=True)
    currencyCode = serializers.CharField(write_only=True)

    class Meta:
        model = TripAdvancePayment
        fields = (
            'tripUf',
            'driverUf',
            'paymentMethodCode',
            'currencyCode',
            'trip',
            'driver',
            'amount',
            'currency',
            'payment_method',
            'purpose',
        )
        read_only_fields = ['trip', 'driver']

    def validate(self, attrs):
        request = self.context['request']

        user_company = get_user_company(request.user)

        # 🔹 resolve Trip
        try:
            trip = Trip.objects.get(
                uf=attrs.pop('tripUf'),
                company=user_company
            )
        except Trip.DoesNotExist:
            raise serializers.ValidationError({
                'tripUf': 'Invalid trip'
            })

        # 🔹 resolve Driver
        try:
            driver = User.objects.get(
                uf=attrs.pop('driverUf'),
                company=user_company
            )
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'driverUf': 'Invalid driver'
            })

      # 🔹 resolve PaymentMethod
        try:
            payment_method = PaymentMethod.objects.get(
                code=attrs.pop('paymentMethodCode'),
            )
        except PaymentMethod.DoesNotExist:
            raise serializers.ValidationError({
                'paymentMethodCode': 'Invalid payment method'
            })
        # 🔒 enforce ownership / system rule
        if payment_method.is_system:
            if payment_method.company is not None:
                raise serializers.ValidationError({
                    'payment_method': 'Invalid system payment method configuration'
                })
        else:
            if payment_method.company != user_company:
                raise serializers.ValidationError({
                    'payment_method': 'Payment method not allowed for this company'
                })

         # 🔹 resolve Trip
        try:
            currency = Currency.objects.get(
                currency_code=attrs.pop('currencyCode')
            )
        except Currency.DoesNotExist:
            raise serializers.ValidationError({
                'currencyCode': 'Invalid trip'
            })

        # 🔒 business rules
        if not trip.drivers.filter(pk=driver.pk).exists():
            raise serializers.ValidationError(
                "Driver is not assigned to this trip"
            )

        # 🔁 inject resolved instances
        attrs['trip'] = trip
        attrs['driver'] = driver
        attrs['payment_method'] = payment_method
        attrs['currency'] = currency

        return attrs

    def create(self, validated_data):
        request = self.context['request']

        status_requested = TripAdvancePaymentStatus.objects.get(
            code='requested'
        )

        user_company = get_user_company(request.user)

        return TripAdvancePayment.objects.create(
            company=user_company,
            created_by=request.user,
            status=status_requested,
            **validated_data
        )


class TripAdvancePaymentChangeStatusSerializer(serializers.Serializer):
    status = serializers.CharField()

    def validate_status(self, value):
        try:
            return TripAdvancePaymentStatus.objects.get(code=value)
        except TripAdvancePaymentStatus.DoesNotExist:
            raise serializers.ValidationError("Invalid status")


class LoadDocumentItemSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    id = serializers.IntegerField(required=False)
    version = serializers.IntegerField(required=False)
    uf = serializers.UUIDField(required=False)
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        uf = obj.get("uf")
        if not uf:
            return None
        return f"{settings.BACKEND_URL}/api/load-documents/{uf}/"


###### START LOAD INV ######


class LoadInvListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="company.company_name", read_only=True)
    load_uf = serializers.CharField(source="load.uf", read_only=True)
    load_sn = serializers.CharField(source="load.sn", read_only=True)
    customer = serializers.CharField(
        source="load.bill_to.company_name", read_only=True)
    status_load_inv = serializers.CharField(
        source="status", read_only=True)
    issued_by_name = serializers.SerializerMethodField(read_only=True)
    original_amount_currency = serializers.SerializerMethodField(
        read_only=True)
    amount_mdl = serializers.SerializerMethodField(
        read_only=True)
    exchange_rate = serializers.SerializerMethodField(
        read_only=True)

    class Meta:
        model = LoadInv
        fields = [
            "company",
            "company_name",
            "load_uf",
            "load_sn",
            "customer",
            "invoice_number",
            "issued_date",
            "amount_mdl",
            "original_amount_currency",
            "currency",
            "exchange_rate",
            "rate_date",
            "status_load_inv",
            "invoice_type",
            "issued_at",
            "issued_by",
            "issued_by_name",
            "uf",
        ]

    def get_issued_by_name(self, obj):
        user = obj.issued_by
        return user.get_full_name() or user.email

    def get_original_amount_currency(self, obj):
        if obj.original_amount is None:
            return None

        amount_rounded = obj.original_amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return f"{amount_rounded} {obj.currency}"

    def get_amount_mdl(self, obj):
        if obj.amount_mdl is None:
            return None

        amount_rounded = obj.amount_mdl.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return f"{amount_rounded}"

    def get_exchange_rate(self, obj):
        if obj.exchange_rate is None:
            return None

        amount_rounded = obj.exchange_rate.quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP
        )

        return f"{amount_rounded}"

###### END LOAD INV ######
