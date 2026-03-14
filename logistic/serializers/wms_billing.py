from django.db.models import Sum
from rest_framework import serializers

from abb.utils import get_user_company
from logistic.models import WHBillingCharge, WHBillingInvoice, WHBillingInvoiceLine, WHBillingPeriod


class WHBillingPeriodSerializer(serializers.ModelSerializer):
    charges_count = serializers.SerializerMethodField(read_only=True)
    total_charges_amount = serializers.SerializerMethodField(read_only=True)
    documents_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WHBillingPeriod
        fields = [
            "uf",
            "start_date",
            "end_date",
            "is_closed",
            "created_at",
            "charges_count",
            "total_charges_amount",
            "documents_count",
        ]
        read_only_fields = [
            "uf",
            "created_at",
            "charges_count",
            "total_charges_amount",
            "documents_count",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        company = get_user_company(request.user)

        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("start_date must be <= end_date")

        qs = WHBillingPeriod.objects.filter(company=company)

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if start_date and end_date:
            overlaps = qs.filter(
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).exists()

            if overlaps:
                raise serializers.ValidationError("Billing period overlaps with an existing period")

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        company = get_user_company(request.user)
        return WHBillingPeriod.objects.create(company=company, **validated_data)

    def get_company(self):
        request = self.context.get("request")
        return get_user_company(request.user)

    def get_charges_count(self, obj):
        company = self.get_company()
        return WHBillingCharge.objects.filter(
            company=company,
            billing_period=obj,
        ).count()

    def get_total_charges_amount(self, obj):
        company = self.get_company()
        total = (
            WHBillingCharge.objects.filter(
                company=company,
                billing_period=obj,
            ).aggregate(s=Sum("total"))["s"]
            or 0
        )
        return str(total)

    def get_documents_count(self, obj):
        company = self.get_company()
        return WHBillingInvoice.objects.filter(
            company=company,
            period=obj,
        ).count()


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
        read_only=True,
    )
    contact_name = serializers.CharField(source="contact.company_name", read_only=True)
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


class WHIssueBillingDocumentsSerializer(serializers.Serializer):
    period = serializers.CharField()
    contacts = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class WHBillingInvoiceManualLineCreateItemSerializer(serializers.Serializer):
    charge_type = serializers.CharField(default="manual")
    description = serializers.CharField(max_length=250)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=4)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price must be zero or greater")
        return value


class WHBillingInvoiceManualLinesCreateSerializer(serializers.Serializer):
    lines = WHBillingInvoiceManualLineCreateItemSerializer(many=True)