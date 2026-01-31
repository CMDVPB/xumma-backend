from rest_framework import serializers
from .models import Calendar, CalendarEvent, CalendarMember


class CalendarSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = Calendar
        fields = ["id", "name", "display_name", "is_me", "uf",
                  ]

    def get_display_name(self, obj):
        user = obj.created_by
        if not user:
            return ""

        first = user.first_name or ""
        last = user.last_name or ""

        full_name = f"{first} {last}".strip()

        if full_name:
            return full_name

        return user.email

    def get_is_me(self, obj):
        request = self.context.get("request")
        return bool(request and obj.created_by_id == request.user.id)


class CalendarEventSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    owner_email = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    owner_id = serializers.UUIDField(
        source="calendar.created_by.uf", read_only=True)
    calendar_id = serializers.UUIDField(source="calendar.uf", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "calendar",
            "title",
            "description",
            "start",
            "end",
            "all_day",
            "color",
            "owner_name",
            "owner_email",
            "is_mine",
            "owner_id",
            "calendar_id",
            "uf",
        ]

    def _get_owner(self, obj):
        return obj.calendar.created_by if obj.calendar else None

    def get_owner_name(self, obj):
        user = self._get_owner(obj)
        if not user:
            return ""

        first = user.first_name or ""
        last = user.last_name or ""

        full_name = f"{first} {last}".strip()

        if full_name:
            return full_name

        return user.email

    def get_owner_email(self, obj):
        user = self._get_owner(obj)
        return user.email if user else ""

    def get_is_mine(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        return obj.calendar.created_by_id == request.user.id


class CalendarMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarMember
        fields = ("calendar", "user", "role")
        read_only_fields = ("calendar", "user", "role")


class AvailableCalendarSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    is_subscribed = serializers.BooleanField()

    class Meta:
        model = Calendar
        fields = (
            "name",
            "color",
            "is_default",
            "display_name",
            "is_subscribed",
            "uf",
        )

    def get_display_name(self, obj):
        user = obj.created_by
        if not user:
            return ""

        first = user.first_name or ""
        last = user.last_name or ""

        full_name = f"{first} {last}".strip()

        if full_name:
            return full_name

        return user.email
