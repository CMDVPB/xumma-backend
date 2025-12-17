import time
from datetime import datetime
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


import logging

from abb.mixins_serializer import ReadWriteSerializerMixin
from abb.pagination import LimitResultsSetPagination
from abb.permissions import AssignedUserManagerOrReadOnlyIfLocked, AssignedUserOrManagerOrReadOnly, HasGroupPermission
from abb.utils import check_not_unique_num, check_not_unique_num_inv, get_user_company, is_valid_queryparam
from axx.models import Inv
from ayy.models import Comment, ItemInv
from dff.serializers.serializers_inv import InvListSerializer, InvSerializer
logger = logging.getLogger(__name__)


User = get_user_model()


class InvListView(ListAPIView):
    pagination_class = LimitResultsSetPagination
    serializer_class = InvListSerializer
    http_method_names = ['head', 'get']
    permission_classes = [IsAuthenticated, HasGroupPermission]
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Inv.objects.filter(company__id=user_company.id)

            queryset = queryset.select_related(
                'bill_to', 'bill_to__country_code_post').select_related('status').select_related('currency')

            comments = Comment.objects.all()

            itemInvs = ItemInv.objects.select_related(
                'item_for_item_inv').all()

            queryset = queryset.prefetch_related(
                Prefetch('inv_comments', queryset=comments)).prefetch_related(
                Prefetch('iteminv_invs', queryset=itemInvs))

            # print('7878')

            return queryset.distinct()

        except Exception as e:
            print('E357', e)
            return Inv.objects.none()

    def filter_queryset(self, queryset: QuerySet, **kwargs):
        queryset = super().filter_queryset(queryset=queryset, **kwargs)
        order_by = 'date_inv'

        try:
            myitems = self.request.query_params.get('myitems', None)
            text_query = self.request.query_params.get('textQuery', None)

            if is_valid_queryparam(myitems) and myitems == 'myitems':
                queryset = queryset.filter(
                    assigned_user_id=self.request.user.id)

            if text_query is not None:
                print('6060', text_query)
                queryset = queryset.filter(Q(vn__icontains=text_query) | Q(an__icontains=text_query) | Q(load__sn__icontains=text_query)
                                           | Q(bill_to__company_name__icontains=text_query)
                                           #                        | Q(
                                           # load_tors__tn__icontains=text_query) | Q(load_ctrs__cn__icontains=text_query) | Q(
                                           # load_invs__qn__icontains=text_query) | Q(load_invs__vn__icontains=text_query) | Q(
                                           # load_exps__xn__icontains=text_query) | Q(hb__icontains=text_query) | Q(mb__icontains=text_query) | Q(
                                           # booking_number__icontains=text_query) | Q(customer_ref__icontains=text_query) | Q(
                                           #     customer_notes__icontains=text_query) | Q(load_address__icontains=text_query) | Q(
                                           #         unload_address__icontains=text_query)
                                           )

            else:

                sortByQuery = self.request.query_params.get(
                    'sortByQuery', None)
                quoteQuery = self.request.query_params.get('quoteQuery', None)
                billtoQuery = self.request.query_params.get(
                    'billtoQuery', None)
                shipperQuery = self.request.query_params.get(
                    'shipperQuery', None)
                load_detailQuery = self.request.query_params.get(
                    "load_detailQuery", None)
                load_addressQuery = self.request.query_params.get(
                    'load_addressQuery', None)
                unload_addressQuery = self.request.query_params.get(
                    'unload_addressQuery', None)
                countryLoadQuery = self.request.query_params.get(
                    'countryLoadQuery', None)
                countryUnloadQuery = self.request.query_params.get(
                    'countryUnloadQuery', None)
                docDateDueMinQuery = self.request.query_params.get(
                    'docDateDueMinQuery', None)
                docDateDueMaxQuery = self.request.query_params.get(
                    'docDateDueMaxQuery', None)
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

                # print('8485', myitems, type(myitems), quoteQuery, type(quoteQuery))

                if is_valid_queryparam(sortByQuery):
                    if sortByQuery is not None:
                        if sortByQuery == '0':
                            order_by = 'vn' if quoteQuery is None else 'qn'
                        elif sortByQuery == '1':
                            order_by = 'date_inv'
                        elif sortByQuery == '2':
                            order_by = 'status__order_number'
                        else:
                            order_by = 'date_inv'

                if is_valid_queryparam(quoteQuery):
                    is_quote = True if quoteQuery == '1' else False
                    queryset = queryset.filter(is_quote=is_quote)

                if is_valid_queryparam(billtoQuery):
                    queryset = queryset.filter(bill_to__uf=billtoQuery)

                if is_valid_queryparam(shipperQuery):
                    queryset = queryset.filter(
                        entry_invs__shipper__uf=shipperQuery)

                if is_valid_queryparam(load_detailQuery):
                    queryset = queryset.filter(
                        load_detail__icontains=load_detailQuery)

                if is_valid_queryparam(load_addressQuery):
                    queryset = queryset.filter(
                        load_address__icontains=load_addressQuery)

                if is_valid_queryparam(unload_addressQuery):
                    queryset = queryset.filter(
                        unload_address__icontains=unload_addressQuery)

                if is_valid_queryparam(countryLoadQuery):
                    queryset = queryset.filter(
                        inv_entries__country_load__value=countryLoadQuery)

                if is_valid_queryparam(countryUnloadQuery):
                    queryset = queryset.filter(
                        inv_entries__country_unload__value=countryUnloadQuery)

                if is_valid_queryparam(docDateDueMinQuery):
                    queryset = queryset.filter(
                        date_due__gte=docDateDueMinQuery)

                if is_valid_queryparam(docDateDueMaxQuery):
                    queryset = queryset.filter(
                        date_due__lte=docDateDueMaxQuery)

                if is_valid_queryparam(currencyQuery):
                    queryset = queryset.filter(currency=currencyQuery)

                if is_valid_queryparam(modeQuery):
                    queryset = queryset.filter(mode__serial_number=modeQuery)

                if is_valid_queryparam(statusQuery):
                    queryset = queryset.filter(
                        status__serial_number=statusQuery)

                if is_valid_queryparam(dateMinQuery):
                    queryset = queryset.filter(date_inv__gte=dateMinQuery)

                if is_valid_queryparam(dateMaxQuery):
                    queryset = queryset.filter(date_inv__lte=dateMaxQuery)

                if is_valid_queryparam(numMinQuery):
                    if quoteQuery:
                        queryset = queryset.filter(qn__gte=numMinQuery)
                    else:
                        queryset = queryset.filter(vn__gte=numMinQuery)

                if is_valid_queryparam(numMaxQuery):
                    if quoteQuery:
                        queryset = queryset.filter(qn__lte=numMaxQuery)
                    else:
                        queryset = queryset.filter(vn__lte=numMaxQuery)

                if is_valid_queryparam(relDocNumQuery):
                    queryset = queryset.filter(Q(qn__icontains=relDocNumQuery) | Q(vn__icontains=relDocNumQuery) | Q(
                        load__sn__icontains=relDocNumQuery))

                if is_valid_queryparam(iteminvQuery):
                    queryset = queryset.filter(
                        iteminv_invs__item_for_item_inv=iteminvQuery)

                if is_valid_queryparam(commentQuery):
                    queryset = queryset.filter(
                        inv_comments__comment__icontains=commentQuery)

            return queryset.order_by(F(order_by).desc(nulls_first=True),
                                     '-date_created')

        except Exception as e:
            print('E737', e)
            return queryset


class InvCreateView(CreateAPIView):
    pagination_class = LimitResultsSetPagination
    serializer_class = InvSerializer
    http_method_names = ['head', 'post']
    permission_classes = [IsAuthenticated,
                          HasGroupPermission
                          # IsSubscriptionActiveOrReadOnly
                          ]
    lookup_field = 'uf'
    required_groups = {
        'HEAD': ['type_forwarder'],
        'POST': ['type_forwarder'],
    }

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Inv.objects.filter(company__id=user_company.id)

            return queryset
        except:
            print('E437')
            return []

    def post(self, request, *args, **kwargs):

        num = ''
        is_quote = self.request.data.get('is_quote', None)
        if is_quote:
            num = 'qn'
        else:
            num = 'vn'

        # print('7700', num)

        item = None
        queryset = self.get_queryset()
        new_item_num = self.request.data.get(num, None)
        series = self.request.data.get('series')

        if (num == 'vn' and check_not_unique_num_inv(queryset=queryset, new_item_num=new_item_num, num=num, series=series)) or \
                (num == 'qn' and check_not_unique_num(item, queryset, new_item_num, num)):
            return Response(status=status.HTTP_409_CONFLICT)

        # print('7708', num)

        user_company = get_user_company(request.user)

        entry_invs = request.data.get('entry_invs', None)
        if entry_invs:
            for entry in entry_invs:
                shipper = entry.get('shipper', None)
                if shipper:
                    shipper['owner'] = model_to_dict(self.request.user)
                else:
                    pass

        for item_for_item_inv in request.data.get('iteminv_invs', None):
            item_for_item_inv = item_for_item_inv.get(
                'item_for_item_inv', None)
            if item_for_item_inv:
                item_for_item_inv['company'] = user_company

        # print('7724')

        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        try:
            # print('3892', )
            user_company = get_user_company(self.request.user)
            assigned_user_uf = self.request.data.get('assigned_user', None)

            if assigned_user_uf is not None:
                assigned_user = User.objects.get(uf=assigned_user_uf)
            else:
                assigned_user = User.objects.get(uf=self.request.user.uf)

            serializer.save(company=user_company,
                            assigned_user=assigned_user)

        except Exception as e:
            print('EV581', e)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvDetailView(ReadWriteSerializerMixin, RetrieveUpdateDestroyAPIView):
    read_serializer_class = InvSerializer
    write_serializer_class = InvSerializer
    lookup_field = 'uf'
    http_method_names = ['head', 'get', 'patch', 'delete']
    permission_classes = [IsAuthenticated, HasGroupPermission, AssignedUserOrManagerOrReadOnly,
                          AssignedUserManagerOrReadOnlyIfLocked
                          #   IsSubscriptionActiveOrReadOnly
                          ]
    required_groups = {
        'HEAD': ['type_forwarder'],
        'GET': ['type_forwarder'],
        'PATCH': ['type_forwarder'],
        'DELETE': ['type_forwarder'],
    }

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        queryset = Inv.objects.filter(company__id=user_company.id)

        # print('7799', )
        return queryset

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        num = 'qn' if self.request.data.get('qn', None) else 'vn'
        # print('5673', num)

        queryset = self.get_queryset().exclude(uf=instance.uf)
        new_item_num = self.request.data.get(num, None)
        series = self.request.data.get('series')

        if (num == 'vn' and check_not_unique_num_inv(queryset=queryset, new_item_num=new_item_num, num=num, series=series)) or \
                (num == 'qn' and check_not_unique_num(instance, queryset, new_item_num, num)):
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

        except Exception as e:
            logger.error(f'EV403 InvDetail. perform_update. Error: {e}')

        serializer.save(changed_by=self.request.user,
                        assigned_user=assigned_user)
