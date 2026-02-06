

from rest_framework import serializers
from .models import DocumentTemplate, DocumentTemplateTranslation


class DocumentTemplateTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplateTranslation
        fields = ('language', 'body_html')


class DocumentTemplateSerializer(serializers.ModelSerializer):
    body_html = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = (
            'uf',
            'type',
            'code',
            'label',
            'body_html',
        )

    def get_body_html(self, obj):
        language = self.context.get('language')

        if not language:
            return None

        translation = obj.template_document_translations.filter(
            language=language
        ).first()

        return translation.body_html if translation else None
