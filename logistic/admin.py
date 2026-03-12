from django.contrib import admin

from logistic.models import (WHBillingCharge, WHBillingInvoice, WHBillingInvoiceLine, WHBillingPeriod, WHContactTariffHandlingTierOverride, WHContactTariffOverride, WHInbound,
                              WHInboundLine, WHLocation, WHOutbound, WHOutboundLine, WHProduct, WHStock, WHStockLedger
                              )



@admin.register(WHLocation)
class WHLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name', 'is_active',
                    )


@admin.register(WHProduct)
class WHProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'owner', 'sku',
                    )


@admin.register(WHInbound)
class WHInboundAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'owner', 'reference', 'status',                  
                    'received_at', 'received_by',
                      'created_by', 'created_at', 
                      'updated_at',
                     
                    )
    
    
@admin.register(WHInboundLine)
class WHInboundLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'inbound', 'product', 'location', 'quantity', 'pallets', 'pallet_type', 'area_m2', 'volume_m3', 'note',
                    )

@admin.register(WHStock)
class WHStockAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'owner', 'product', 'location', 
                    'quantity', 'pallets', 'pallet_type', 'area_m2', 'volume_m3', 'updated_at',                     
                    )

                 
@admin.register(WHStockLedger)
class WHStockLedgerAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'product', 'location', 
                    'delta_quantity', 'delta_pallets', 'delta_area_m2', 'delta_volume_m3', 
                    'source_type', 'source_uf', 'actor_user', 'actor_portal', 'created_at', 
                    'movement_direction',
                    )


@admin.register(WHOutbound)
class WHOutboundAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'owner', 'reference', 'status',
                    'created_by_user', 'created_by_portal', 'contact_person', 
                    'planned_pickup_at', 'shipped_at', 'created_at', 'updated_at',
                     
                    )


@admin.register(WHOutboundLine)
class WHOutboundLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'outbound', 'product', 'location', 'quantity', 'pallets', 'pallet_type', 'area_m2', 'volume_m3', 'note',
                    )


@admin.register(WHBillingInvoice)
class WHBillingInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'contact', 'period', 'total_amount',
                    'created_at', 'status',
                    )



@admin.register(WHBillingInvoiceLine)
class WHBillingInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'charge_type', 'description', 'quantity', 'unit_price', 'total', 'created_at',
                    )



@admin.register(WHBillingCharge)
class WHBillingChargeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'contact', 'billing_period', 'charge_type',                    
                    )


@admin.register(WHBillingPeriod)
class WHBillingPeriodAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'start_date', 'end_date', 'is_closed', 'created_at',                 
                    )


@admin.register(WHContactTariffOverride)
class WHContactTariffOverrideAdmin(admin.ModelAdmin):
    list_display = ('id', 'contact', 'storage_mode', 'storage_per_euro_pallet_per_day', 'storage_per_iso2_pallet_per_day',
                     'storage_per_block_pallet_per_day', 'storage_per_m2_per_day', 'storage_per_m3_per_day', 'storage_per_unit_per_day',                 
                    )




@admin.register(WHContactTariffHandlingTierOverride)
class WHContactTariffHandlingTierOverrideAdmin(admin.ModelAdmin):
    list_display = ('id', 'override', 'fee_type', 'unit', 'min_quantity',
                     'max_quantity', 'price', 'order',
                    )















