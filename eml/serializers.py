
from collections import defaultdict
import queue
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField
from rest_framework.validators import UniqueTogetherValidator
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.constants import EMAIL_TEMPLATE_CODES
from abb.utils import get_user_company
from ayy.models import EmailTemplate, EmailTemplateTranslation, MailLabelV2, MailMessage


User = get_user_model()


class EmailTemplateSerializer(serializers.ModelSerializer):
    languages = serializers.SerializerMethodField()
    translations = serializers.SerializerMethodField()
    created_by = SlugRelatedField(
        slug_field='uf',
        read_only=True,
    )

    def get_languages(self, obj):
        return list(
            obj.template_email_translations.values_list(
                "language", flat=True)
        )

    def get_translations(self, obj):
        """
        Returns:
        {
          "ro": { "subject": "...", "body": "..." },
          "en": { "subject": "...", "body": "..." }
        }
        """
        translations = {}

        for t in obj.template_email_translations.all():
            translations[t.language] = {
                "subject": t.subject,
                "body": t.body,
            }

        return translations

    class Meta:
        model = EmailTemplate
        fields = ["code", "label", "description", "languages", "created_by", "created_at", "updated_at", "uf",
                  'company',
                  'translations',
                  ]
        read_only_fields = ["company", "created_by", 'uf']


class EmailTemplateTranslationCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(allow_blank=True, required=True)
    body = serializers.CharField(allow_blank=True, required=True)


class EmailTemplateCreateSerializer(serializers.ModelSerializer):
    translations = serializers.DictField(
        child=EmailTemplateTranslationCreateSerializer()
    )

    class Meta:
        model = EmailTemplate
        fields = (
            "code",
            "label",
            "description",
            "translations",
        )

    def validate_translations(self, value):
        if not value:
            raise serializers.ValidationError(
                "At least one language is required."
            )

        for lang, data in value.items():
            if len(lang) != 2:
                raise serializers.ValidationError(
                    f"Invalid language code: {lang}"
                )

            if "subject" not in data or "body" not in data:
                raise serializers.ValidationError(
                    f"Subject and body are required for language '{lang}'."
                )

            if not isinstance(data.get("subject"), str) or not isinstance(data.get("body"), str):
                raise serializers.ValidationError(
                    f"Subject and body must be strings for language '{lang}'."
                )

        return value

    def validate_code(self, value):
        if value not in EMAIL_TEMPLATE_CODES:
            raise serializers.ValidationError(
                "Invalid template code."
            )
        return value

    def create(self, validated_data):
        request = self.context["request"]
        translations_data = validated_data.pop("translations")

        user_company = get_user_company(request.user)

        template = EmailTemplate.objects.create(
            company=user_company,
            created_by=request.user,
            **validated_data
        )

        translations = [
            EmailTemplateTranslation(
                template=template,
                language=lang,
                subject=data["subject"],
                body=data["body"],
            )
            for lang, data in translations_data.items()
        ]

        EmailTemplateTranslation.objects.bulk_create(translations)

        return template


class EmailTemplateTranslationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateTranslation
        fields = ("language", "subject", "body")


class EmailTemplateDetailSerializer(serializers.ModelSerializer):
    translations = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = (
            "uf",
            "code",
            "label",
            "description",
            "translations",
            "created_at",
        )

    def get_translations(self, obj):
        """
        Return translations as:
        {
          "ro": { subject, body },
          "en": { subject, body }
        }
        """
        return {
            t.language: {
                "subject": t.subject,
                "body": t.body,
            }
            for t in obj.template_email_translations.all()
        }


class EmailTemplateTranslationUpsertSerializer(serializers.Serializer):
    subject = serializers.CharField(
        max_length=255, required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)


class EmailTemplateUpdateSerializer(serializers.ModelSerializer):
    translations = serializers.DictField(
        child=EmailTemplateTranslationUpsertSerializer(),
        required=False
    )

    class Meta:
        model = EmailTemplate
        fields = ("code", "label", "description", "translations", "updated_at")

    def validate_code(self, value):
        if value not in EMAIL_TEMPLATE_CODES:
            raise serializers.ValidationError(
                "Invalid template code."
            )

        request = self.context["request"]
        template = self.instance
        # Enforce unique (company, code) on update
        user_company = get_user_company(request.user)
        exists = EmailTemplate.objects.filter(
            company=user_company,
            code=value
        ).exclude(id=template.id).exists()
        if exists:
            raise serializers.ValidationError(
                "This code is already used in your company.")
        return value

    def validate_translations(self, value):
        # languages keys must be 2 chars
        for lang in value.keys():
            if len(lang) != 2:
                raise serializers.ValidationError(
                    f"Invalid language code: {lang}")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context["request"]
        method = self.context.get("method")  # "PUT" or "PATCH"

        translations_data = validated_data.pop("translations", None)

        # Update main template fields
        for field, val in validated_data.items():
            setattr(instance, field, val)
        instance.save()

        # If translations not provided, we're done
        if translations_data is None:
            return instance

        # Upsert translations
        existing = {
            t.language: t
            for t in EmailTemplateTranslation.objects.filter(template=instance)
        }

        to_create = []
        to_update = []

        for lang, data in translations_data.items():
            subj = data.get("subject", None)
            body = data.get("body", None)

            # For PUT, require both subject and body for each provided language
            if method == "PUT":
                if subj is None or body is None:
                    raise serializers.ValidationError(
                        {"translations": {
                            lang: "Both subject and body are required for PUT."}}
                    )

            # For PATCH, allow partial updates but at least one field must be present
            if method == "PATCH":
                if subj is None and body is None:
                    raise serializers.ValidationError(
                        {"translations": {lang: "Provide subject and/or body."}}
                    )

            if lang in existing:
                t = existing[lang]
                if subj is not None:
                    t.subject = subj
                if body is not None:
                    t.body = body
                to_update.append(t)
            else:
                # For new translation, we need both subject+body
                if subj is None or body is None:
                    raise serializers.ValidationError(
                        {"translations": {lang: "New language requires subject and body."}}
                    )
                to_create.append(
                    EmailTemplateTranslation(
                        template=instance,
                        language=lang,
                        subject=subj,
                        body=body,
                    )
                )

        if to_create:
            EmailTemplateTranslation.objects.bulk_create(to_create)

        if to_update:
            EmailTemplateTranslation.objects.bulk_update(
                to_update, ["subject", "body"])

        # Optional behavior:
        # If PUT, treat as "replace translations": delete languages that were not sent
        if method == "PUT":
            EmailTemplateTranslation.objects.filter(template=instance).exclude(
                language__in=translations_data.keys()
            ).delete()

        return instance


### Mail Labels and Messages Serializers ###


class MailLabelV2Serializer(serializers.ModelSerializer):
    class Meta:
        model = MailLabelV2
        fields = ["id", "slug", "name", "type", "order"]


class MailMessageListSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at")
    isRead = serializers.BooleanField(source="is_read")
    to = serializers.SerializerMethodField()

    class Meta:
        model = MailMessage
        fields = [
            "id",
            "subject",
            "createdAt",
            "isRead",
            "to",
        ]

    def get_to(self, obj):
        # obj.to is JSONField → list of strings
        return [{"email": email} for email in (obj.to or [])]


class MailMessageDetailSerializer(serializers.ModelSerializer):
    message = serializers.CharField(source="body")
    createdAt = serializers.DateTimeField(source="created_at")

    from_ = serializers.SerializerMethodField()
    to = serializers.SerializerMethodField()
    labelIds = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    isRead = serializers.BooleanField(source="is_read")
    isStarred = serializers.SerializerMethodField()
    isImportant = serializers.SerializerMethodField()

    class Meta:
        model = MailMessage
        fields = [
            "id",
            "subject",
            "message",
            "createdAt",
            "from_",
            "to",
            "labelIds",
            "isRead",
            "isStarred",
            "isImportant",
            "attachments",
        ]

    def get_from_(self, obj):
        email = obj.from_email or ""

        return {
            "name": email.split("@")[0] if email else "Sistem",
            "email": email,
            "avatarUrl": None,
        }

    def get_to(self, obj):
        return [{"email": email} for email in (obj.to or [])]

    def get_labelIds(self, obj):
        return list(obj.labels.values_list("slug", flat=True))

    def get_attachments(self, obj):
        return []

    def get_isStarred(self, obj):
        return False

    def get_isImportant(self, obj):
        return False
