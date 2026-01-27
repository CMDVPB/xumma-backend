from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.utils import timezone

from abb.models import Currency
from abb.utils import get_user_company
from auu.models import PaymentMethod
from axx.models import Trip, TripAdvancePayment, TripAdvancePaymentStatus

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
