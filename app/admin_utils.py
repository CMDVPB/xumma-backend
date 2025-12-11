from django.contrib import admin


class DocumentSeriesNumberRangeFilter(admin.SimpleListFilter):
    title = "Document number in range"
    parameter_name = "document_number"

    def lookups(self, request, model_admin):
        return []  # No dropdown, we use the text input

    def queryset(self, request, queryset):
        value = self.value()
        if value and value.isdigit():
            number = int(value)
            return queryset.filter(number_from__lte=number, number_to__gte=number)
        return queryset
