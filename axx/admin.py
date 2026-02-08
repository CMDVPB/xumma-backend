from django.contrib import admin

from axx.models import Inv, Load, LoadDocument, LoadEvent, LoadInv, Trip, TripAdvancePayment, TripAdvancePaymentStatus, TripDriver


@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'sn', 'is_loaded',
                    'is_cleared', 'is_unloaded', 'is_invoiced')


@admin.register(LoadInv)
class LoadInvAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'load', 'issued_date', 'amount_mdl',
                    )


@admin.register(LoadDocument)
class LoadDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'load', 'doc_type', 'file',
                    )


@admin.register(LoadEvent)
class LoadEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'load', 'event_type', 'created_at', )


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'vehicle_tractor', 'vehicle_trailer')


@admin.register(TripDriver)
class TripDriverAdmin(admin.ModelAdmin):
    list_display = ('id', )


@admin.register(Inv)
class InvAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'bill_to')


@admin.register(TripAdvancePaymentStatus)
class TripAdvancePaymentStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code',
                    'name',
                    'is_final',
                    'serial_number',)


@admin.register(TripAdvancePayment)
class TripAdvancePaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'trip',
                    'driver',
                    'amount',
                    'currency',)
