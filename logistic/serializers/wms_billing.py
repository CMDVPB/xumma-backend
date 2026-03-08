from rest_framework import serializers

from logistic.models import WHBillingInvoice, WHBillingInvoiceLine, WHBillingPeriod



class WHBillingPeriodSerializer(serializers.ModelSerializer):

    class Meta:
        model = WHBillingPeriod
        fields = [
            "uf",
            "start_date",
            "end_date",
            "is_closed",
            "created_at",
        ]


class WHBillingInvoiceLineSerializer(serializers.ModelSerializer):

    class Meta:
        model = WHBillingInvoiceLine
        fields = [
            "uf",
            "charge_type",
            "description",
            "quantity",
            "unit_price",
            "total",
        ]


class WHBillingInvoiceSerializer(serializers.ModelSerializer):

    lines = WHBillingInvoiceLineSerializer(
        source="invoice_wh_lines",
        many=True,
        read_only=True
    )

    contact_name = serializers.CharField(
        source="contact.company_name",
        read_only=True
    )

    period = WHBillingPeriodSerializer(read_only=True)

    class Meta:
        model = WHBillingInvoice
        fields = [
            "uf",
            "contact",
            "contact_name",
            "period",
            "total_amount",
            "status",
            "created_at",
            "lines",
        ]