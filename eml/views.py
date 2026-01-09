

from rest_framework import status, permissions
import json
import logging
from django.utils import timezone
from datetime import timedelta
from datetime import datetime, timedelta
from smtplib import SMTPException
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.cache import cache
from django.http import HttpResponse
from django.db.models import QuerySet, Prefetch, Q, F
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import exceptions
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from abb.utils import get_user_company
from ayy.models import EmailTemplate, EmailTemplateTranslation, MailLabelV2, MailMessage, UserEmail, UserEmailAttachment
from eml.serializers import EmailTemplateCreateSerializer, EmailTemplateDetailSerializer, EmailTemplateSerializer, \
    EmailTemplateUpdateSerializer, MailLabelV2Serializer, MailMessageDetailSerializer, MailMessageListSerializer
from eml.tasks import send_basic_email_task
from eml.utils import safe_json_list


logger = logging.getLogger(__name__)

### System email service ###


class BasicEmailOptionalAttachmentsView(APIView):
    '''
    Using celery task to send basic email.
    '''
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, format=None):
        to = safe_json_list(request.data.get('to'))
        cc = safe_json_list(request.data.get('cc'))

        if not to:
            return Response(
                {"detail": "Recipient list is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        files = request.FILES.getlist("attachments")  # 👈 optional

        with transaction.atomic():
            email = UserEmail.objects.create(
                user=user,
                from_email=settings.DEFAULT_FROM_EMAIL_AWS,
                to=to,
                cc=cc,
                subject=request.data.get('subject', ''),
                body=request.data.get('body', ''),
                status='queued'
            )

            print('3348', files)

            # 📎 Save attachments (if any)
            for f in files:
                UserEmailAttachment.objects.create(
                    email=email,
                    file=f,
                    filename=f.name,
                    size=f.size,
                )

            ### safe get-or-create "Sent" label ###
            sent_label, _ = MailLabelV2.objects.get_or_create(
                user=user,
                slug="sent",
                defaults={
                    "name": "Sent",
                    "type": MailLabelV2.SYSTEM,
                    "order": 2,
                },
            )

            mailbox_msg = MailMessage.objects.create(
                user=user,
                sent_email=email,
                from_email=email.from_email,
                to=email.to,
                subject=email.subject,
                body=email.body,
                is_read=True,
            )

            mailbox_msg.labels.add(sent_label)

            ### enqueue task ###
            send_basic_email_task.delay(email.id)

            return Response(
                {
                    "detail": "Email queued for sending",
                    "mailbox_id": mailbox_msg.id,
                    "email_attachments": len(files),
                },
                status=status.HTTP_202_ACCEPTED
            )


### Email Templates ###


class EmailTemplateCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EmailTemplateCreateSerializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        template = serializer.save()

        return Response(
            {
                "uf": template.uf,
                "message": "Email template created successfully."
            },
            status=status.HTTP_201_CREATED
        )


class EmailTemplatesListView(ListAPIView):
    '''
    List available email templates.
    '''
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # print('4472', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = EmailTemplate.objects.filter(
                company__id=user_company.id)

            queryset = queryset.select_related(
                'company',
                'created_by',
            )

            template_email_translations_qs = EmailTemplateTranslation.objects.all()

            queryset = queryset.prefetch_related(
                Prefetch('template_email_translations',
                         queryset=template_email_translations_qs),
            )

            # print('4484', )

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRROLOG6581 EmailTemplatesListView. get_queryset. Error: {e}')
            return EmailTemplate.objects.none()


class EmailTemplateUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, uf):
        user_company = get_user_company(request.user)
        return get_object_or_404(EmailTemplate, uf=uf, company=user_company)

    def get(self, request, uf):
        """
        Retrieve email template with all translations
        """
        template = self.get_object(request, uf)

        serializer = EmailTemplateDetailSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, uf):
        """
        Partial update (recommended for editing one language)
        """
        template = self.get_object(request, uf)

        serializer = EmailTemplateUpdateSerializer(
            template,
            data=request.data,
            partial=True,
            context={"request": request, "method": "PATCH"}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Template updated."}, status=status.HTTP_200_OK)

    def put(self, request, uf):
        """
        Full replace (recommended for "Save all languages")
        """
        template = self.get_object(request, uf)

        serializer = EmailTemplateUpdateSerializer(
            template,
            data=request.data,
            partial=False,
            context={"request": request, "method": "PUT"}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Template replaced."}, status=status.HTTP_200_OK)


### Mail Labels and Messages ###
class MailLabelV2ListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MailLabelV2Serializer

    def get_queryset(self):
        return MailLabelV2.objects.filter(
            user=self.request.user
        ).order_by("order")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({"labels": response.data})


class MailListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MailMessageListSerializer

    def get_queryset(self):
        label_slug = self.request.query_params.get("labelId")
        since = timezone.now() - timedelta(days=31)

        return (
            (MailMessage.objects
             .select_related("sent_email")
             .prefetch_related("labels")
             .filter(
                 user=self.request.user,
                 labels__slug=label_slug,
                 created_at__gte=since,   # ✅ last 31 days
             )
             .order_by("-created_at")
             )

        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({"mails": response.data})


class MailDetailAPIView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MailMessageDetailSerializer

    def get_queryset(self):
        return MailMessage.objects.filter(user=self.request.user)

    def get(self, request):
        mail_id = request.query_params.get("mailId")

        mail = get_object_or_404(
            MailMessage,
            id=mail_id,
            user=request.user,
        )

        if not mail.is_read:
            mail.is_read = True
            mail.save(update_fields=["is_read"])

        serializer = MailMessageDetailSerializer(mail)
        return Response({"mail": serializer.data})
