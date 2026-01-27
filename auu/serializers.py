from rest_framework import serializers

from auu.models import PaymentMethod


class PaymentMethodListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            'code',
            'label',
            'is_active',
            'uf',
        )

    def validate(self, attrs):
        request = self.context['request']

        payment_method = attrs.get('payment_method')

        if not payment_method:
            return attrs  # handled elsewhere (required field)

        if payment_method.company and payment_method.company != request.user.company:
            raise serializers.ValidationError({
                'payment_method': 'Invalid payment method'
            })

        if not payment_method.is_active:
            raise serializers.ValidationError({
                'payment_method': 'Inactive payment method'
            })

        return attrs
