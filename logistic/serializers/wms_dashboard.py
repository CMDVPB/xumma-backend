from rest_framework import serializers


class WmsDashboardCustomerItemSerializer(serializers.Serializer):
    uf = serializers.CharField()
    name = serializers.CharField()
    value = serializers.DecimalField(max_digits=18, decimal_places=2)


class WmsDashboardCustomersSummarySerializer(serializers.Serializer):
    top_revenue_customers = WmsDashboardCustomerItemSerializer(many=True)
    customers_by_pallet_usage = WmsDashboardCustomerItemSerializer(many=True)
    inactive_customers = WmsDashboardCustomerItemSerializer(many=True)