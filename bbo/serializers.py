from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):

    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "severity",
            "due_date",
            "related_object_type",
            "related_object_id",
            "is_read",

            "payload",
        ]

    def get_is_read(self, obj):
        user = self.context["request"].user

        return obj.read_states.filter(user=user).exists()


###### START APP TOP REVENUE CUSTOMERS ######

class TopCustomerSerializer(serializers.Serializer):
    bill_to_id = serializers.IntegerField()
    bill_to_name = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=4)


class TopCustomersBlockSerializer(serializers.Serializer):
    period = serializers.IntegerField()
    customers = TopCustomerSerializer(many=True)

###### END APP TOP REVENUE CUSTOMERS ######
