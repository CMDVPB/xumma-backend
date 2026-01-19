import time
from datetime import datetime
from datetime import timedelta
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.utils import timezone
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.db import IntegrityError
from django.db.models import QuerySet, Prefetch, Q, F
from django.core.exceptions import PermissionDenied
from djoser import signals
from djoser.compat import get_user_email
from djoser.email import ActivationEmail, ConfirmationEmail
from rest_framework import permissions, status, exceptions
from rest_framework import generics, mixins
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # used for FBV
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError

from abb.constants import LOAD_SIZE, LOAD_TYPES
from abb.pagination import CustomInfiniteCursorPagination, LimitResultsSetPagination
from abb.permissions import AssignedUserManagerOrReadOnlyIfLocked, AssignedUserOrManagerOrReadOnly
from abb.utils import get_user_company, is_valid_queryparam
from app.utils import is_user_member_group
from axx.models import Ctr, Exp, Inv, Load, Tor
from ayy.models import CMR, Comment, Entry, ImageUpload, ItemInv


import logging

from dff.serializers.serializers_load import LoadListForTripSerializer, LoadListSerializer, LoadPatchSerializer, LoadSerializer
logger = logging.getLogger(__name__)


User = get_user_model()


class LoadListView(ListAPIView):
    ''' Get list of loads'''
    pagination_class = CustomInfiniteCursorPagination
    serializer_class = LoadListSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uf'

    def get_queryset(self):
        # print('2358', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = Load.objects.filter(company__id=user_company.id)

            queryset = queryset.select_related(
                'assigned_user',
                'bill_to',
                'bill_to__country_code_post',
                'trip',
                'mode',
                'bt',
                'currency',
                'status',
                'incoterm',
                'payment_term',
                'carrier',
                'carrier__country_code_post',
                'vehicle_tractor',
                'vehicle_trailer',
            )

            comments_qs = Comment.objects.all()

            tors_qs = (Tor.objects
                       .select_related(
                           'carrier',
                           'vehicle_tractor',
                           'vehicle_trailer'
                       )
                       .only('is_tor',
                             'uf',
                             'carrier',
                             'vehicle_tractor',
                             'vehicle_trailer')
                       .filter(company__id=user_company.id)
                       )

            entries_qs = (Entry.objects
                          .select_related(
                              'shipper',
                              'shipper__country_code_site',
                          )
                          .prefetch_related('entry_details')
                          .all())

            itemInvs_qs = ItemInv.objects.select_related(
                'item_for_item_inv', 'item_for_item_cost').all()

            load_imageuploads_qs = ImageUpload.objects.filter(
                company__id=user_company.id)

            queryset = queryset.prefetch_related(
                Prefetch('load_comments', queryset=comments_qs),
                Prefetch('load_tors', queryset=tors_qs),
                Prefetch('entry_loads', queryset=entries_qs),
                Prefetch('load_iteminvs', queryset=itemInvs_qs),
                Prefetch('load_imageuploads', queryset=load_imageuploads_qs),
            )

            # print('2366', )

            return queryset.distinct()

        except Exception as e:
            logger.error(f'EV235 LoadListView. get_queryset. Error: {e}')
            return Load.objects.none()

    def filter_queryset(self, queryset: QuerySet, **kwargs):
        # print('2234',)

        queryset = super().filter_queryset(queryset=queryset, **kwargs)

        order_by = 'date_order'

        try:
            myitems = self.request.query_params.get('myitems', None)
            text_query = self.request.query_params.get('textQuery', None)

            if is_valid_queryparam(myitems) and myitems == 'myitems':
                queryset = queryset.filter(
                    assigned_user__id=self.request.user.id)

            if text_query is not None:
                # print('2020', text_query)
                queryset = queryset.filter(
                    Q(sn__icontains=text_query) |
                    Q(hb__icontains=text_query) |
                    Q(mb__icontains=text_query) |
                    Q(booking_number__icontains=text_query) |
                    Q(customer_ref__icontains=text_query) |
                    Q(customer_notes__icontains=text_query) |
                    Q(load_address__icontains=text_query) |
                    Q(unload_address__icontains=text_query) |
                    Q(trip__rn__icontains=text_query) |
                    Q(bill_to__company_name__icontains=text_query) |
                    Q(carrier__company_name__icontains=text_query) |
                    Q(carrier__alias_company_name__icontains=text_query) |
                    Q(vehicle_tractor__reg_number__icontains=text_query) |
                    Q(vehicle_trailer__reg_number__icontains=text_query) |
                    Q(load_tors__tn__icontains=text_query) |
                    Q(load_tors__vehicle_tractor__reg_number__icontains=text_query) |
                    Q(load_tors__vehicle_trailer__reg_number__icontains=text_query) |
                    Q(load_ctrs__cn__icontains=text_query) |
                    Q(load_invs__qn__icontains=text_query) |
                    Q(load_invs__vn__icontains=text_query) |
                    Q(load_exps__xn__icontains=text_query)
                )

            else:
                button_index = self.request.query_params.get(
                    'buttonIndex', None)
                button_index_30 = self.request.query_params.get(
                    'buttonIndex30', None)
                type_loading_query = self.request.query_params.get(
                    'typeLoadingQuery', None)
                sortByQuery = self.request.query_params.get(
                    'sortByQuery', None)
                billtoQuery = self.request.query_params.get(
                    'billtoQuery', None)
                shipperQuery = self.request.query_params.get(
                    'shipperQuery', None)
                carrierQuery = self.request.query_params.get(
                    'carrierQuery', None)
                hbMbNumQuery = self.request.query_params.get(
                    'hbMbNumQuery', None)
                load_detailQuery = self.request.query_params.get(
                    "load_detailQuery", None)
                load_addressQuery = self.request.query_params.get(
                    'load_addressQuery', None)
                unload_addressQuery = self.request.query_params.get(
                    'unload_addressQuery', None)
                tractorQuery = self.request.query_params.get(
                    'tractorQuery', None)
                trailerQuery = self.request.query_params.get(
                    'trailerQuery', None)
                countryLoadQuery = self.request.query_params.get(
                    'countryLoadQuery', None)
                countryUnloadQuery = self.request.query_params.get(
                    'countryUnloadQuery', None)
                dateMinQuery = self.request.query_params.get(
                    'dateMinQuery', None)
                dateMaxQuery = self.request.query_params.get(
                    'dateMaxQuery', None)
                numMinQuery = self.request.query_params.get(
                    'numMinQuery', None)
                numMaxQuery = self.request.query_params.get(
                    'numMaxQuery', None)
                relDocNumQuery = self.request.query_params.get(
                    'relDocNumQuery', None)
                iteminvQuery = self.request.query_params.get(
                    'iteminvQuery', None)
                currencyQuery = self.request.query_params.get(
                    'currencyQuery', None)
                modeQuery = self.request.query_params.get('modeQuery', None)
                statusQuery = self.request.query_params.get(
                    'statusQuery', None)
                commentQuery = self.request.query_params.get(
                    'commentQuery', None)
                assignedUserQuery = self.request.query_params.get(
                    'assignedUserQuery', None)
                vehicleQuery = self.request.query_params.get(
                    'vehicleQuery', None)
                startDate = self.request.query_params.get(
                    'startDate', None)
                endDate = self.request.query_params.get(
                    'endDate', None)
                is_cleared_query = self.request.query_params.get(
                    'isClearedQuery', None)

                if is_valid_queryparam(button_index):
                    if is_cleared_query != '1':
                        if button_index == '0':
                            queryset = (queryset
                                        .filter(
                                            Q(trip__isnull=True) &
                                            Q(is_active=True))
                                        )
                        elif button_index == '1':
                            queryset = (queryset
                                        .filter(
                                            Q(is_active=False)
                                        ))
                        elif button_index == '4':
                            queryset = (queryset
                                        .filter(
                                            load_type=LOAD_TYPES[1][0])
                                        )
                        else:
                            pass
                    elif is_cleared_query == '1':
                        if button_index == 'true':
                            queryset = queryset.filter(is_paid=True)

                if is_valid_queryparam(button_index_30):
                    if button_index_30 == 'true':
                        queryset = queryset.filter(load_type=LOAD_TYPES[1][0])
                    else:
                        pass

                if is_valid_queryparam(type_loading_query):
                    if type_loading_query == 'ltl':
                        queryset = queryset.filter(load_size=LOAD_SIZE[0][0])
                    elif type_loading_query == 'ftl':
                        queryset = queryset.filter(load_size=LOAD_SIZE[1][0])
                    elif type_loading_query == 'xpr':
                        queryset = queryset.filter(load_type=LOAD_SIZE[2][0])
                    else:
                        pass

                print('2040', vehicleQuery)

                if is_valid_queryparam(sortByQuery):
                    if sortByQuery == '0':
                        order_by = 'sn'
                    elif sortByQuery == '1':
                        order_by = 'date_order'
                    elif sortByQuery == '2':
                        order_by = 'status__order_number'
                    else:
                        order_by = 'date_order'

                if is_valid_queryparam(billtoQuery):
                    queryset = queryset.filter(bill_to__uf=billtoQuery)

                if is_valid_queryparam(shipperQuery):
                    queryset = queryset.filter(
                        entry_loads__shipper__uf=shipperQuery)

                if is_valid_queryparam(carrierQuery):
                    queryset = queryset.filter(carrier__uf=carrierQuery)

                if is_valid_queryparam(hbMbNumQuery):
                    queryset = queryset.filter(Q(hb__icontains=hbMbNumQuery) | Q(
                        mb__icontains=hbMbNumQuery) | Q(booking_number__icontains=hbMbNumQuery))

                if is_valid_queryparam(load_detailQuery):
                    queryset = queryset.filter(Q(customer_ref__icontains=load_detailQuery) | Q(
                        customer_notes__icontains=load_detailQuery))

                if is_valid_queryparam(load_addressQuery):
                    queryset = queryset.filter(
                        load_address__icontains=load_addressQuery)

                if is_valid_queryparam(unload_addressQuery):
                    queryset = queryset.filter(
                        unload_address__icontains=unload_addressQuery)

                if is_valid_queryparam(tractorQuery):
                    queryset = queryset.filter(
                        vehicle_tractor__uf=tractorQuery)

                if is_valid_queryparam(trailerQuery):
                    queryset = queryset.filter(
                        vehicle_trailer__uf=trailerQuery)

                if is_valid_queryparam(countryLoadQuery):
                    queryset = queryset.filter(Q(entry_loads__action='loading')
                                               & Q(entry_loads__shipper__country_code_site__value=countryLoadQuery))

                if is_valid_queryparam(countryUnloadQuery):
                    queryset = queryset.filter(Q(entry_loads__action='unloading')
                                               & Q(entry_loads__shipper__country_code_site__value=countryUnloadQuery))

                if is_valid_queryparam(currencyQuery):
                    queryset = queryset.filter(currency=currencyQuery)

                if is_valid_queryparam(modeQuery):
                    queryset = queryset.filter(mode__serial_number=modeQuery)

                if is_valid_queryparam(statusQuery):
                    queryset = queryset.filter(
                        status__serial_number=statusQuery)

                if is_valid_queryparam(dateMinQuery):
                    queryset = queryset.filter(date_order__gte=dateMinQuery)

                if is_valid_queryparam(dateMaxQuery):
                    queryset = queryset.filter(date_order__lte=dateMaxQuery)

                if is_valid_queryparam(numMinQuery):
                    queryset = queryset.filter(sn__gte=numMinQuery)

                if is_valid_queryparam(numMaxQuery):
                    queryset = queryset.filter(sn__lte=numMaxQuery)

                if is_valid_queryparam(relDocNumQuery):
                    queryset = queryset.filter(Q(sn__icontains=relDocNumQuery) | Q(trip__rn__icontains=relDocNumQuery) | Q(
                        load_tors__tn__icontains=relDocNumQuery) | Q(load_ctrs__cn__icontains=relDocNumQuery) | Q(load_invs__qn__icontains=relDocNumQuery) | Q(load_invs__vn__icontains=relDocNumQuery) | Q(load_exps__xn__icontains=relDocNumQuery))

                if is_valid_queryparam(iteminvQuery):
                    queryset = queryset.filter(
                        load_iteminvs__item_for_item_inv=iteminvQuery)

                if is_valid_queryparam(commentQuery):
                    queryset = queryset.filter(
                        load_comments__comment__icontains=commentQuery)

                if is_valid_queryparam(assignedUserQuery):
                    queryset = queryset.filter(
                        assigned_user__email=assignedUserQuery)

                if is_valid_queryparam(vehicleQuery):
                    queryset = queryset.filter(Q(trip__vehicle_tractor__uf=vehicleQuery)
                                               | Q(trip__vehicle_trailer__uf=vehicleQuery)
                                               )

                if is_valid_queryparam(startDate):
                    dts = parse_datetime(startDate)
                    if dts:
                        if timezone.is_naive(dts):
                            dts = timezone.make_aware(dts)
                        queryset = queryset.filter(
                            date_order__gt=dts - timedelta(days=1))

                if is_valid_queryparam(endDate):
                    dte = parse_datetime(endDate)
                    if dte:
                        if timezone.is_naive(dte):
                            dte = timezone.make_aware(dte)

                        queryset = queryset.filter(
                            date_order__lt=dte + timedelta(days=1))

                if is_valid_queryparam(is_cleared_query):
                    if is_cleared_query == '1':
                        queryset = queryset.filter(is_cleared=True)

                # print('2260', queryset.count())

            return queryset.distinct().order_by(F(order_by).desc(nulls_first=True),
                                                '-date_created')

        except Exception as e:
            logger.error(
                f'ERRORLOG3935 LoadListView. filter_queryset. Error: {e}')
            return queryset


class LoadCreateView(CreateAPIView):
    pagination_class = LimitResultsSetPagination
    serializer_class = LoadSerializer
    permission_classes = [IsAuthenticated
                          #   IsSubscriptionActiveOrReadOnly
                          ]
    lookup_field = 'uf'
    http_method_names = ['head', 'post']

    def get_queryset(self):
        user = self.request.user
        user_company = get_user_company(user)
        queryset = Load.objects.filter(company__id=user_company.id)
        return queryset

    def post(self, request, *args, **kwargs):
        # print('5547',)

        new_item_num = request.data.get('sn')
        # Fast uniqueness check
        if new_item_num and Load.objects.filter(company=user_company, sn=new_item_num).exists():
            return Response({"detail": f"SN already exists"}, status=status.HTTP_409_CONFLICT)

        user = request.user
        user_company = get_user_company(user)
        # company_current_active_subscription, company_membership = get_company_current_membership(
        #     user_company)
        # load_count_current_month = Load.objects.\
        #     filter(company=user_company, date_created__gte=datetime.today().replace(
        #         day=1, hour=0, minute=0, second=0, microsecond=0)).count()
        # membership_limits = {
        #     'basic': NUMBER_OF_LOADS_ALLOWED[0],
        #     'pro': NUMBER_OF_LOADS_ALLOWED[1],
        #     'premium': NUMBER_OF_LOADS_ALLOWED[2],
        #     'elite': NUMBER_OF_LOADS_ALLOWED[3],
        #     'enterprise': NUMBER_OF_LOADS_ALLOWED[4],
        # }

        # if load_count_current_month >= membership_limits.get(company_membership, 0):
        #     return Response(status=status.HTTP_402_PAYMENT_REQUIRED)

        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        try:
            assigned_user = None

            user_company = get_user_company(self.request.user)
            assigned_user_uf = self.request.data.get('assigned_user', None)

            if assigned_user_uf is not None:
                assigned_user = User.objects.get(uf=assigned_user_uf)
            else:
                assigned_user = User.objects.get(uf=self.request.user.uf)

            serializer.save(company=user_company,
                            assigned_user=assigned_user)

        except Exception as e:
            logger.error(f'EV105 LoadCreateView. perform_create. Error: {e}')
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoadDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = LoadSerializer
    permission_classes = [IsAuthenticated, AssignedUserOrManagerOrReadOnly,
                          AssignedUserManagerOrReadOnlyIfLocked
                          # IsSubscriptionActiveOrReadOnly
                          ]
    http_method_names = ['head', 'get', 'patch', 'delete']
    lookup_field = 'uf'

    def get_serializer_class(self):
        # Use a different serializer for PATCH & simpleload requests

        data = self.request.data
        load_status_update = data.get('loadStatusUpdate', False)

        # print('5680', data)

        if self.request.method == "PATCH" and load_status_update:
            return LoadPatchSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        try:
            user_company = get_user_company(self.request.user)

            # FAST queryset for update/delete
            if self.request.method in ["PATCH", "DELETE"]:
                return Load.objects.filter(company__id=user_company.id)

            queryset = Load.objects.filter(company__id=user_company.id).select_related(
                "assigned_user",
                "bill_to", "bill_to__country_code_post",
                "trip",
                "mode",
                "bt",
                "currency",
                "status",
                "incoterm",
                "carrier",
                "driver",
                "vehicle_tractor",
                "vehicle_trailer",
                "payment_term",
                "person",
            )

            comments_qs = Comment.objects.all()

            entries_qs = Entry.objects.select_related(
                'shipper',
                'shipper__country_code_site',
            ).prefetch_related('entry_details').all()

            itemInvs_qs = ItemInv.objects.select_related(
                'item_for_item_inv').select_related('item_for_item_cost').all()

            load_tors_qs = Tor.objects.filter(
                company__id=user_company.id).select_related('carrier').prefetch_related(
                Prefetch('entry_tors', queryset=entries_qs))

            load_ctrs_qs = Ctr.objects.filter(
                company__id=user_company.id).select_related('bill_to', 'bill_to__country_code_post').prefetch_related(
                Prefetch('entry_ctrs', queryset=entries_qs),
                Prefetch('ctr_iteminvs', queryset=itemInvs_qs)
            )

            load_inv_qs = Inv.objects.filter(
                company__id=user_company.id).select_related('bill_to', 'bill_to__country_code_post').prefetch_related(
                Prefetch('iteminv_invs', queryset=itemInvs_qs))

            exp_qs = Exp.objects.filter(
                company__id=user_company.id).select_related('supplier', 'supplier__country_code_post')

            load_imageuploads = ImageUpload.objects.filter(
                company__id=user_company.id)

            cmr_qs = CMR.objects.filter(company_id=user_company.id)

            queryset = queryset.prefetch_related(
                Prefetch('load_comments', queryset=comments_qs),
                Prefetch('entry_loads', queryset=entries_qs),
                Prefetch('load_iteminvs', queryset=itemInvs_qs),
                Prefetch('load_tors', queryset=load_tors_qs),
                Prefetch('load_ctrs', queryset=load_ctrs_qs),
                Prefetch('load_invs', queryset=load_inv_qs),
                Prefetch('load_exps', queryset=exp_qs),
                Prefetch('load_imageuploads', queryset=load_imageuploads),
                Prefetch("cmr", queryset=cmr_qs),
            )

            # print('1199')
            return queryset.distinct()

        except Exception as e:
            logger.error(f'EV339 LoadDetail. get_queryset. Error: {e}')
            return Load.objects.none()

    def update(self, request, *args, **kwargs):
        # print('2280', request.data)

        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        new_sn = self.request.data.get('sn', None)
        if new_sn:
            exists = Load.objects.filter(
                company=instance.company,
                sn=new_sn
            ).exclude(uf=instance.uf).only('id').exists()

            if exists:
                return Response(status=status.HTTP_409_CONFLICT)

        assigned_user_id = instance.assigned_user.id if instance.assigned_user else None
        if not is_user_member_group(request.user, 'level_manager') and assigned_user_id != self.request.user.id:
            request.data.pop('is_locked', None)

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def perform_update(self, serializer):
        assigned_user = None

        try:
            assigned_user_uf = self.request.data.get('assigned_user', None)

            if assigned_user_uf is not None:
                assigned_user = User.objects.get(uf=assigned_user_uf)
            else:
                assigned_user = User.objects.get(uf=self.request.user.uf)

            # print('4944', )

            serializer.save(changed_by=self.request.user,
                            assigned_user=assigned_user)

        except IntegrityError as e:
            # Check if the error is about unique_company_cmr_number
            if 'unique_company_cmr_number' in str(e):
                logger.error(f'EV137 Duplicate CMR number: {e}')
                raise ValidationError("cmr_number_already_exists")
            else:
                logger.error(f'EV137 IntegrityError: {e}')
                raise ValidationError({"detail": "Database integrity error."})

        except Exception as e:
            logger.error(f'EV137 LoadDetail perform_update {e}')
            raise ValidationError({"detail": "failed_to_update_load"})


###### Load list for Trip ######
class LoadListForTripView(ListAPIView):
    ''' Get list of loads for a particular 1 trip'''
    serializer_class = LoadListForTripSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    lookup_field = 'uf'

    def get_queryset(self):
        # print('3240', self.request.user)

        try:
            user_company = get_user_company(self.request.user)
            queryset = Load.objects.filter(company__id=user_company.id)

            queryset = queryset.select_related(
                'bill_to',
                'bill_to__country_code_post',
                'mode',
                'bt',
            )

            entries_qs = (Entry.objects
                          .select_related(
                              'shipper',
                              'shipper__country_code_site',
                          )
                          .prefetch_related('entry_details')
                          .all())

            itemInvs_qs = ItemInv.objects.select_related(
                'item_for_item_inv', 'item_for_item_cost').all()

            comments_qs = Comment.objects.all()

            queryset = queryset.prefetch_related(
                Prefetch('entry_loads', queryset=entries_qs),
                Prefetch('load_iteminvs', queryset=itemInvs_qs),
                Prefetch('load_comments', queryset=comments_qs),

            )

            return queryset.distinct()

        except Exception as e:
            logger.error(f'EV235 LoadListView. get_queryset. Error: {e}')
            return Load.objects.none()

    def filter_queryset(self, queryset: QuerySet, **kwargs):
        # print('3260',)

        queryset = super().filter_queryset(queryset=queryset, **kwargs)

        try:
            trip_uf = self.request.query_params.get('tripUf', None)

            if is_valid_queryparam(trip_uf):
                queryset = queryset.filter(trip__uf=trip_uf)

            return queryset.order_by('-date_created')

        except Exception as e:
            logger.error(
                f'ERRORLOG3919 LoadListForTripView. filter_queryset. Error: {e}')
            return queryset
