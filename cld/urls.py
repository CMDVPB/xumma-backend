from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [
    path("calendar/list/", CalendarListView.as_view()),
    path("calendars/available/",
         AvailableCalendarListView.as_view(),
         name="calendar-available-list",
         ),

    path("calendar/events/", CalendarEventListView.as_view()),
    path("calendar/events/<uuid:event_id>/",
         CalendarEventDetailView.as_view(),
         name="calendar-event-detail",
         ),
    path("calendar/events/create/", CalendarEventCreateView.as_view()),
    path("calendar/events/<int:pk>/update/",
         CalendarEventUpdateView.as_view()),
    path("calendar/events/<int:pk>/delete/",
         CalendarEventDeleteView.as_view()),

    path("activity-logs/<uuid:log_id>/undo/", ActivityUndoView.as_view()),

    path("calendars/<uuid:calendar_uf>/subscribe/",
         CalendarSubscribeView.as_view(),
         name="calendar-subscribe",
         ),
    path("calendars/<uuid:calendar_uf>/unsubscribe/",
         CalendarUnsubscribeView.as_view(),
         name="calendar-unsubscribe",
         ),

]

urlpatterns = format_suffix_patterns(urlpatterns)
