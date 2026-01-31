
from django.contrib import admin

from cld.models import ActivityLog, Calendar, CalendarEvent, CalendarMember


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'created_by', 'action',
                    )


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'created_by', 'name', 'color', 'is_default',
                    )


@admin.register(CalendarMember)
class CalendarMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'calendar', 'role',
                    )


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'created_by', 'calendar', 'title',
                    )
