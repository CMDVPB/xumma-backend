import os
from rest_framework.views import APIView
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
import logging
import smtplib
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.db.models.deletion import RestrictedError
from django.db.models import QuerySet, Prefetch, Q, F
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView, \
    CreateAPIView, DestroyAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions, status, exceptions
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
import mimetypes
from django.http import FileResponse, Http404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from abb.utils import assign_new_num, get_company_manager, get_user_company
from app.models import SMTPSettings, UserSettings
from app.serializers import UserSettingsSerializer
from att.models import BankAccount, ContactSite, ContractReferenceDate, Note, PaymentTerm, Person, Term
from axx.models import Load
from ayy.models import CMR, AuthorizationStockBatch, CMRStockBatch, CTIRStockBatch, ColliType, ImageUpload, ItemForItemCost, ItemForItemInv
from ayy.serializers import ItemForItemCostSerializer
from dff.serializers.serializers_bce import BankAccountSerializer, ImageUploadInSerializer, ImageUploadOutSerializer, NoteSerializer
from dff.serializers.serializers_document import AuthorizationStockBatchSerializer, CMRStockBatchSerializer, CTIRStockBatchSerializer
from dff.serializers.serializers_entry_detail import ColliTypeSerializer
from dff.serializers.serializers_item_inv import ItemForItemInvSerializer
from dff.serializers.serializers_other import ContactSiteListSerializer, ContactSiteSerializer, PaymentTermSerializer, PersonSerializer, TermSerializer
from dtt.serializers import ContractReferenceDateSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class UserSettingsView(RetrieveUpdateDestroyAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Always return settings for the currently logged-in user
        settings, _ = UserSettings.objects.get_or_create(
            user=self.request.user)
        return settings

    def patch(self, request, *args, **kwargs):
        # print('5748', request.data)
        return self.partial_update(request, *args, **kwargs)


class CMRStockBatchListCreateView(ListCreateAPIView):
    serializer_class = CMRStockBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = CMRStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG691 CMRStockBatchView. get_queryset. Error: {e}')
            return CMRStockBatch.objects.none()


class CMRStockBatchDetailsView(RetrieveUpdateDestroyAPIView):
    serializer_class = CMRStockBatchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = CMRStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG691 CMRStockBatchView. get_queryset. Error: {e}')
            return CMRStockBatch.objects.none()


class AuthorizationStockBatchListCreateView(ListCreateAPIView):
    serializer_class = AuthorizationStockBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = AuthorizationStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG691 AuthorizationStockBatchListCreateView. get_queryset. Error: {e}')
            return AuthorizationStockBatch.objects.none()


class AuthorizationStockBatchDetailsView(RetrieveUpdateDestroyAPIView):
    serializer_class = AuthorizationStockBatchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = AuthorizationStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG657 AuthorizationStockBatchDetailsView. get_queryset. Error: {e}')
            return AuthorizationStockBatch.objects.none()


class CTIRStockBatchListCreateView(ListCreateAPIView):
    serializer_class = CTIRStockBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = CTIRStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG691 CTIRStockBatchListCreateView. get_queryset. Error: {e}')
            return CTIRStockBatch.objects.none()


class CTIRStockBatchDetailsView(RetrieveUpdateDestroyAPIView):
    serializer_class = CTIRStockBatchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            queryset = CTIRStockBatch.objects.filter(
                company__id=user_company.id)

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG657 CTIRStockBatchDetailsView. get_queryset. Error: {e}')
            return CTIRStockBatch.objects.none()


class ContactSiteListView(ListAPIView):
    serializer_class = ContactSiteListSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        # print('ContactSiteListView get_queryset 2050')
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = ContactSite.objects.select_related(
                'contact', 'company').filter(company__id=user_company.id).order_by('-date_modified')

            return queryset.distinct()

        except Exception as e:
            logger.error(
                f'ERRORLOG573 ContactSiteListView get_queryset. ERROR: {e}')
            return ContactSite.objects.none()


class ContactSiteCreateView(CreateAPIView):
    serializer_class = ContactSiteListSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return ContactSite.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG329 ContactSiteCreate. get_queryset. Error: {e}')
            return ContactSite.objects.none()

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG331 ContactSiteCreate. perform_create. Error: {e}')
            serializer.save()


class ContactSiteDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ContactSiteSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return ContactSite.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG5097 ContactSiteDetailView get_queryset. ERROR: {e}')
            return ContactSite.objects.none()

    def perform_update(self, serializer):
        try:
            serializer.save()
        except RestrictedError as e:
            raise ValidationError(
                {"detail": "entry_not_deleted_used_in_related_documents"}, code=400)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {'error': 'restricted'},
                status=status.HTTP_400_BAD_REQUEST
            )


class BankAccountListCreateView(ListCreateAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return BankAccount.objects.filter(company__id=user_company.id).distinct().order_by('currency_code')
        except Exception as e:
            print('E557', e)
            return BankAccount.objects.none()

    def get(self, request, *args, **kwargs):
        # Without bank accounts related to contacts
        filtered_bank_accounts = self.get_queryset().filter(contact=None)
        serializer = BankAccountSerializer(filtered_bank_accounts, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        try:
            user_company = get_user_company(self.request.user)
            serializer.save(company=user_company)

        except Exception as e:
            print('EV381', e)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BankAccountDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'put', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)

            queryset = BankAccount.objects.filter(Q(
                contact__company__id=user_company.id) | Q(company__id=user_company.id))

            queryset = queryset.select_related(
                'contact').select_related('contact__company')

            return queryset.distinct()
        except Exception as e:
            print('EV451', e)
            return BankAccount.objects.none()


class ItemForItemInvListCreateView(ListCreateAPIView):
    serializer_class = ItemForItemInvSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = ItemForItemInv.objects.filter(
                company__id=user_company.id)

            return queryset.distinct().order_by('description')
        except Exception as e:
            logger.error(f'EV735 ItemForItemInvListCreate: {e}')
            return ItemForItemInv.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        user_company = get_user_company(user)

        description = request.data.get('description', '').strip()
        # default True if not provided
        is_sale = request.data.get('is_sale', True)

        # Check for duplicates only within the same is_sale type
        if self.get_queryset().filter(description__iexact=description, is_sale=is_sale).exists():
            return Response(status=status.HTTP_409_CONFLICT)

        # Save company association automatically if needed
        request.data['company'] = user_company.id

        return super().create(request, *args, **kwargs)


class ItemForItemInvDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItemForItemInvSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = ItemForItemInv.objects.filter(
                company__id=user_company.id)

            return queryset.order_by('description')
        except Exception as e:
            print('E735', e)
            return ItemForItemInv.objects.none()

    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        request_obj = request.data.get('description', None).lower()
        is_sale = request.data.get('is_sale', True)

        # print('332211', is_sale)

        if (instance.description.lower() == request_obj) or \
                not self.get_queryset().filter(description__iexact=request_obj, is_sale=is_sale).exists():
            return self.update(request, *args, **kwargs)
        else:
            return Response(status=status.HTTP_409_CONFLICT)

    def delete(self, request, uf):
        obj = self.get_object()  # this triggers DRF permission checks
        try:
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except IntegrityError:
            return Response(
                {'error': 'restricted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ItemForItemInv.DoesNotExist:
            return Response(
                {'error': 'Object not found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class ItemForItemCostListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItemForItemCostSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)
            queryset = (ItemForItemCost.objects
                        .select_related(
                            'company')
                        .filter(
                            Q(is_system=True) |
                            Q(company__id=user_company.id))
                        )

            queryset = queryset.distinct().order_by('serial_number', 'description')

            return queryset
        except Exception as e:
            logger.error(
                f'ERRORLOG4119 ItemForItemCostListCreateView. get_queryset. ERROR: {e}')
            return ItemForItemCost.objects.none()

    def post(self, request, *args, **kwargs):
        request_obj = request.data.get('description', None).lower()

        if not self.get_queryset().filter(description__iexact=request_obj).exists():
            return self.create(request, *args, **kwargs)
        else:
            return Response(status=status.HTTP_409_CONFLICT)

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG4669 ItemForItemCostListCreateView. perform_create. ERROR: {e}')
            serializer.save()


class ItemForItemCostDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ItemForItemCostSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = ItemForItemCost.objects.select_related(
                'company').filter(company__id=user_company.id)
            return queryset
        except Exception as e:
            logger.error(
                f'EV575 ItemForItemCostDetailView. get_queryset. Error: {e}')
            return ItemForItemCost.objects.none()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        request_obj = request.data.get('description', None).lower()
        if instance is not None and ((instance.description.lower() != request_obj) and
                                     self.get_queryset().filter(description__iexact=request_obj).exists()):
            return Response(status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class NoteListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated,]
    serializer_class = NoteSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)
            return Note.objects.filter(company__id=user_company.id).distinct().order_by('-note_short')
        except Exception as e:
            print('E245', e)
            return Note.objects.none()

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(company=user_company)


class NoteDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = NoteSerializer
    http_method_names = ['get', 'patch', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Note.objects.filter(
                company__id=user_company.id).distinct()
            return queryset
        except Exception as e:
            print('E247', e)
            return Note.objects.none()


class PaymentTermListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentTermSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)
            return PaymentTerm.objects.filter(company__id=user_company.id).distinct().order_by('-payment_term_short')
        except Exception as e:
            return PaymentTerm.objects.none()

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(company=user_company)


class PaymentTermsDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentTermSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = PaymentTerm.objects.filter(
                company__id=user_company.id).distinct()
            return queryset
        except Exception as e:
            print('E247', e)
            return PaymentTerm.objects.none()


class TermListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TermSerializer

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return Term.objects.filter(company__id=user_company.id).distinct()

        except Exception as e:
            print('E533', e)
            return Term.objects.none()

    def post(self, request, *args, **kwargs):
        if not self.get_queryset().filter(term_short__iexact=request.data.get('term_short', None)).exists():
            return self.create(request, *args, **kwargs)
        else:
            raise exceptions.ValidationError(
                detail='not_unique', )

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            serializer.save(company=user_company)
        except:
            print('E297')
            serializer.save()


class TermDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TermSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return Term.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            print('E293', e)
            return Term.objects.none()

    def put(self, request, *args, **kwargs):
        # print('9870', request.data)
        instance = self.get_object()
        if not self.get_queryset().filter(term_short__iexact=request.data.get('term_short', None)).exists() \
                or instance.term_short.lower() == request.data.get('term_short', None).lower():
            return self.update(request, *args, **kwargs)

        else:
            raise exceptions.ValidationError(
                detail='not_unique', )


class ColliTypeListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ColliTypeSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            return (
                ColliType.objects
                .filter(
                    Q(company_id=user_company.id) |
                    Q(is_system=True)
                )
                .order_by('serial_number')
                .distinct()
            )

        except Exception:
            return ColliType.objects.none()

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(company=user_company)


class PersonDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = PersonSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)

            qs = (Person.objects
                        .select_related(
                            'contact',
                            'contact__company',
                            'site',
                            'site__company',
                        )
                  .filter(
                            Q(contact__company__id=user_company.id) |
                            Q(site__company__id=user_company.id)
                        )
                  )

            return qs
        except Exception as e:
            logger.error(
                f'ERRORLOG3373 PersonDetail. get_queryset. Error: {e}')
            return Person.objects.none()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except Exception as e:
            logger.error(f'ERRORLOG3393 PersonDetail. destroy. Error: {e}')
            raise ValidationError(
                detail="entry_not_deleted_used_in_related_documents")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImageView(CreateAPIView, RetrieveUpdateDestroyAPIView):
    serializer_class = ImageUploadInSerializer
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)
            # print('5682', user_company)
            return ImageUpload.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(f'ERRORV741 ImageView. get_queryset. Error: {e}')
            return ImageUpload.objects.none()

    def perform_create(self, serializer):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            # print('4642', user_company)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(f'ERRORV461 ImageView. perform_create. Error: {e}')
            serializer.save()


class MediaProxyView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, uf):
        image = get_object_or_404(ImageUpload, uf=uf)

        print('3232', uf)

        # Ownership check
        if image.company != get_user_company(request.user):
            raise Http404()

        file_field = image.file_obj  # FileField

        if not file_field:
            raise Http404()

        # Check physical file existence
        if not os.path.exists(file_field.path):
            # Optional: log this
            # logger.warning("Missing file for ImageUpload %s", image.id)
            raise Http404("File not found")

        content_type, _ = mimetypes.guess_type(file_field.name)
        content_type = content_type or "application/octet-stream"

        response = FileResponse(
            file_field.open("rb"),
            content_type=content_type,
        )

        response["Content-Disposition"] = (
            f'inline; filename="{image.file_name}"'
        )

        return response

    def delete(self, request, uf):
        image = get_object_or_404(ImageUpload, uf=uf)

        # ownership check
        if image.company != get_user_company(request.user):
            raise Http404()

        file_field = image.file_obj

        # delete physical file first
        if file_field and os.path.exists(file_field.path):
            try:
                os.remove(file_field.path)
            except OSError:
                # optional: log error
                pass

        # delete DB record
        image.delete()

        return Response(
            {"detail": "File deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class ContractReferenceDateListCreateView(ListCreateAPIView):
    serializer_class = ContractReferenceDateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        if not user_company:
            return ContractReferenceDate.objects.none()

        return (
            ContractReferenceDate.objects.filter(
                Q(company=user_company) | Q(is_system=True),
                is_active=True
            ).order_by("order", "label")
        )

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)

        serializer.save(
            company=user_company,
            created_by=self.request.user
        )

### Start SMTP Settings ###


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_smtp_connection_view(request):
    """
    Test the SMTP connection using the provided settings by the user.
    """

    try:
        email = request.data.get('email')
        password = request.data.get('password')
        # username = request.data.get('username')
        host = request.data.get('server')
        port = request.data.get('port')
        encryption_type = request.data.get('encryptionType')

        use_tls = True if encryption_type == 'tls' else False
        timeout = 2

        print('V578', email, password, host, port,
              encryption_type, use_tls, timeout)

        # return Response({'error': 'SMTP connection failed', 'details': 'SMTP connection is disabled'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Connect to the SMTP server
            if use_tls:
                server = smtplib.SMTP(host, port, timeout=timeout)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(host, port)

            # Login with provided credentials
            server.login(email, password)
            server.quit()
            return Response({"success": True, "message": "Connection successful!"}, status=status.HTTP_200_OK)

        except smtplib.SMTPException as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print('EV504', e)
        return Response({'error': 'SMTP connection failed', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def get_post_delete_user_smtp_settings(request):
    """
    Get, create,  update, delete SMTP settings for the logged-in user.
    """

    try:
        if request.method == 'GET':
            data_to_send = []
            qs_smpt_setting = SMTPSettings.objects.filter(user=request.user)

            if qs_smpt_setting.count() != 0:
                data_to_send = [
                    {'email': smtp_setting.email, 'replyToEmail': smtp_setting.reply_to_email,
                        'defaultFromName': smtp_setting.default_from_name,
                        'server': smtp_setting.server, 'port': smtp_setting.port,
                        'encryptionType': smtp_setting.encryption_type,
                     'uf': smtp_setting.uf} for smtp_setting in qs_smpt_setting]

                # print('6558', data_to_send)

            return Response(data_to_send, status=status.HTTP_200_OK)
        elif request.method == 'POST':
            user = request.user
            email = request.data.get('email')
            password = request.data.get('password')
            username = request.data.get('username')
            reply_to_email = request.data.get('replyToEmail')
            default_from_name = request.data.get('defaultFromName')
            server = request.data.get('server')
            port = request.data.get('port')
            encryption_type = request.data.get('encryptionType')

            # print('6550', user, request.data)

            smtp_setting, created = SMTPSettings.objects.update_or_create(user=user, defaults={
                'user': user, 'server': server, 'port': port, 'email': email,
                'username': username, 'key': password, 'reply_to_email': reply_to_email, 'default_from_name': default_from_name,
                'encryption_type': encryption_type})

            status_201_or_200 = status.HTTP_201_CREATED if created else status.HTTP_200_OK

            return Response({'email': smtp_setting.email, 'replyToEmail': smtp_setting.reply_to_email,
                             'defaultFromName': smtp_setting.default_from_name, 'uf': smtp_setting.uf}, status=status_201_or_200)
        elif request.method == 'DELETE':
            smtp_setting = SMTPSettings.objects.get(user=request.user)
            smtp_setting.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        else:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # Handle database integrity issues, such as unique constraint violations
    except IntegrityError as e:
        return Response({'error': 'Database error', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Handle validation errors, such as missing or invalid data
    except ValidationError as e:
        return Response({'error': 'Invalid data', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except SMTPSettings.DoesNotExist:
        print('EV531')
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Catch any other unexpected exceptions
    except Exception as e:
        print('EV579', e)
        return Response({'error': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
### End SMTP Settings ###


@api_view(["POST"])
def validate_or_generate_cmr(request, uf):
    """
    POST accepts:
      - cmr_number (optional)
    If provided: checks uniqueness.
    If empty: generates next sequential cmr_number per company.
    """

    # print('V8440', request.data, uf)

    cmr_number = request.data.get("cmr_number", "").strip()

    # Get the load
    try:
        load = Load.objects.get(uf=uf)
    except Load.DoesNotExist:
        return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

    company = load.company

    # Get or create CMR object for this load
    cmr, created = CMR.objects.get_or_create(
        load=load, defaults={"company": company})

    # Case 1: user entered number → validate uniqueness per company
    if cmr_number:
        exists = CMR.objects.filter(
            company=company,
            number=cmr_number
        ).exclude(id=cmr.id).exists()

        if exists:
            return Response(
                {"error": "cmr_number_already_exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cmr.number = cmr_number
        cmr.save(update_fields=["number"])
        return Response({"cmr_number": cmr_number}, status=status.HTTP_200_OK)

    # Case 2: no number provided → generate next sequential number per company
    cmr_qs = CMR.objects.filter(company=company)
    num_new = assign_new_num(cmr_qs, "number")

    cmr.number = num_new
    cmr.save(update_fields=["number"])

    return Response({"cmr_number": num_new}, status=status.HTTP_200_OK)
