from django.contrib import admin

from bbo.models import Notification, NotificationRead


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'type', 'severity', 'related_object_type', 'due_date', 'created_at', 'updated_at',
                    )


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ('id', 'notification', 'user', 'read_at',
                    )
