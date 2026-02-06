from django.contrib import admin

from bab.models import DocumentTemplate, DocumentTemplateTranslation


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'type', 'label',
                    )


@admin.register(DocumentTemplateTranslation)
class DocumentTemplateTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'language',
                    )
