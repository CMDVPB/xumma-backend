from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Exists, OuterRef, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView, GenericAPIView, \
    UpdateAPIView, DestroyAPIView
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response
from rest_framework import status

from abb.utils import get_user_company
from cld.permissions import require_calendar_read, require_calendar_write
from cld.services.activity_log import log_activity
from cld.services.services import undo_event_change


from .models import ActivityLog, Calendar, CalendarEvent, CalendarMember
from .serializers import AvailableCalendarSerializer, CalendarEventSerializer, CalendarSerializer


class CalendarListView(ListAPIView):
    serializer_class = CalendarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Calendar.objects.filter(
            calendarmember__user=self.request.user
        )


class CalendarEventDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CalendarEventSerializer

    def get_object(self):
        event = get_object_or_404(CalendarEvent, id=self.kwargs["event_id"])
        require_calendar_read(self.request.user, event.calendar)
        return event


class CalendarEventCreateView(CreateAPIView):
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        calendar = serializer.validated_data["calendar"]

        # print('6070', calendar)

        if not calendar:
            raise ValidationError({"calendar": "This field is required"})

        require_calendar_write(self.request.user, calendar)

        event = serializer.save(
            calendar=calendar,
            company=calendar.company,
            created_by=self.request.user
        )

        log_activity(
            company=calendar.company,
            user=self.request.user,
            action="event_created",
            entity_type="calendar_event",
            entity_id=event.id,
        )

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "request": self.request,
        }


class CalendarEventUpdateView(UpdateAPIView):
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]
    queryset = CalendarEvent.objects.all()

    def perform_update(self, serializer):
        event = self.get_object()

        require_calendar_write(self.request.user, event.calendar)

        updated = serializer.save()

        log_activity(
            company=event.calendar.company,
            user=self.request.user,
            action="event_updated",
            entity_type="calendar_event",
            entity_id=event.id,
        )

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "request": self.request,
        }


class CalendarEventDeleteView(DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = CalendarEvent.objects.all()

    def perform_destroy(self, instance):
        require_calendar_write(self.request.user, instance.calendar)

        log_activity(
            company=instance.calendar.company,
            user=self.request.user,
            action="event_deleted",
            entity_type="calendar_event",
            entity_id=instance.id,
        )

        instance.delete()


class ActivityUndoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, log_id):
        log = ActivityLog.objects.get(id=log_id)

        undo_event_change(log=log, user=request.user)

        return Response({"status": "ok"})


class CalendarEventListView(ListAPIView):
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(self.request.user)

        # calendars user is a member of
        calendar_ids = CalendarMember.objects.filter(
            user=user
        ).values_list("calendar_id", flat=True)

        qs = CalendarEvent.objects.filter(
            company=user_company,
            calendar_id__in=calendar_ids,
        ).select_related("event_type", "calendar")

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(calendar__created_by__first_name__icontains=search)
                | Q(calendar__created_by__last_name__icontains=search)
                | Q(calendar__created_by__email__icontains=search)
            )

        return qs.distinct()

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "request": self.request,
        }


class CalendarSubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, calendar_uf):
        user_company = get_user_company(request.user)

        try:
            calendar = Calendar.objects.get(
                uf=calendar_uf,
                company=user_company,
            )
        except Calendar.DoesNotExist:
            raise NotFound("Calendar not found")

        # Determine role
        role = "owner" if calendar.created_by_id == request.user.id else "viewer"

        CalendarMember.objects.get_or_create(
            calendar=calendar,
            user=request.user,
            defaults={"role": role},
        )

        return Response(status=204)


class CalendarUnsubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, calendar_uf):
        user_company = get_user_company(request.user)
        calendar = get_object_or_404(
            Calendar,
            uf=calendar_uf,
            company=user_company,
        )

        CalendarMember.objects.filter(
            calendar=calendar,
            user=request.user,
        ).delete()

        return Response(
            {"detail": "Unsubscribed successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class AvailableCalendarListView(ListAPIView):
    serializer_class = AvailableCalendarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        subscribed_qs = CalendarMember.objects.filter(
            calendar=OuterRef("pk"),
            user=user,
        )

        user_company = get_user_company(user)

        return (
            Calendar.objects
            .filter(company=user_company)
            .annotate(is_subscribed=Exists(subscribed_qs))
            .order_by("name")
        )
