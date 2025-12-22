import time
import logging
from datetime import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import QuerySet, Prefetch, Q, F
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from abb.pagination import LimitResultsSetPagination
from abb.permissions import AssignedUserManagerOrReadOnlyIfLocked, HasGroupPermission
from abb.utils import check_not_unique_num, get_user_company, is_valid_queryparam
from app.utils import is_user_member_group
from axx.models import Exp, Load, Tor, Trip
from ayy.models import Comment, Entry, ItemInv, RouteSheet
from dff.serializers.serializers_trip import TripCreateUpdateSerializer, TripListSerializer, TripSerializer

logger = logging.getLogger(__name__)


User = get_user_model()


class TripListView(ListAPIView):
    ''' get list of trips '''
    pagination_class = LimitResultsSetPagination
    serializer_class = TripListSerializer
    permission_classes = [IsAuthenticated, HasGroupPermission]
    required_groups = {
        'OPTIONS': ['type_carrier'],
        'HEAD': ['type_carrier'],
        'GET': ['type_carrier'],
        'POST': ['type_carrier'],
    }

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = Trip.objects.filter(company__id=user_company.id)

            queryset = queryset.select_related(
                'carrier', 'carrier__country_code_post').select_related('status').select_related('bt').\
                select_related('mode').select_related(
                    'vehicle_tractor').select_related('vehicle_trailer')

            lodad_entries = Entry.objects.select_related(
                'shipper', 'shipper__company', 'shipper__country_code_site', 'shipper__country_code_site').\
                prefetch_related('entry_details').all()

            comments_qs = Comment.objects.all()
            trip_loads_qs = Load.objects.filter(company__id=user_company.id).prefetch_related(
                Prefetch('entry_loads', queryset=lodad_entries))

            route_sheet_qs = RouteSheet.objects.filter(
                company__id=user_company.id)

            drivers = user_company.user.all()

            queryset = queryset.prefetch_related(
                Prefetch('trip_comments', queryset=comments_qs),
                Prefetch('trip_loads', queryset=trip_loads_qs),
                Prefetch('trip_route_sheets', queryset=route_sheet_qs),
                Prefetch('drivers', queryset=drivers)
            )

            # print('2828')

            return queryset.distinct()

        except Exception as e:
            print('E557', e)
            return Trip.objects.none()

    def filter_queryset(self, queryset: QuerySet, **kwargs):
        queryset = super().filter_queryset(queryset=queryset, **kwargs)
        order_by = 'date_order'

        # print("2010")

        try:
            myitems = self.request.query_params.get('myitems', None)
            text_query = self.request.query_params.get('textQuery', None)

            print('2030',)

            if is_valid_queryparam(myitems) and myitems == 'myitems':
                queryset = queryset.filter(
                    assigned_user__id=self.request.user.id)

            if text_query is not None:
                print('2036', text_query, type(text_query))
                queryset = queryset.filter(Q(rn__icontains=text_query)
                                           | Q(carrier__company_name__icontains=text_query)
                                           | Q(trip_loads__sn__icontains=text_query)
                                           | Q(vehicle_tractor__reg_number__icontains=text_query)
                                           | Q(vehicle_trailer__reg_number__icontains=text_query)
                                           )

            else:
                sortByQuery = self.request.query_params.get(
                    'sortByQuery', None)
                billtoQuery = self.request.query_params.get(
                    'billtoQuery', None)
                shipperQuery = self.request.query_params.get(
                    'shipperQuery', None)
                clientDriverQuery = self.request.query_params.get(
                    'clientDriverQuery', None)
                tractorQuery = self.request.query_params.get(
                    'tractorQuery', None)
                trailerQuery = self.request.query_params.get(
                    'trailerQuery', None)
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
                modeQuery = self.request.query_params.get('modeQuery', None)
                statusQuery = self.request.query_params.get(
                    'statusQuery', None)
                commentQuery = self.request.query_params.get(
                    'commentQuery', None)
                vehicleQuery = self.request.query_params.get(
                    'vehicleQuery', None)
                startDate = self.request.query_params.get(
                    'startDate', None)
                endDate = self.request.query_params.get(
                    'endDate', None)

                print('3040', startDate)

                if is_valid_queryparam(sortByQuery):
                    if sortByQuery is not None:
                        if sortByQuery == '0':
                            order_by = 'rn'
                        elif sortByQuery == '1':
                            order_by = 'date_order'
                        elif sortByQuery == '2':
                            order_by = 'status__order_number'
                        else:
                            order_by = 'date_order'

                if is_valid_queryparam(billtoQuery):
                    queryset = queryset.filter(carrier__uf=billtoQuery)

                if is_valid_queryparam(shipperQuery):
                    queryset = queryset.filter(
                        trip_loads__entry_loads__shipper__uf=shipperQuery)

                if is_valid_queryparam(clientDriverQuery):
                    queryset = queryset.filter(
                        trip_loads__bill_to__uf=clientDriverQuery)

                if is_valid_queryparam(tractorQuery):
                    queryset = queryset.filter(
                        vehicle_tractor__uf=tractorQuery)

                if is_valid_queryparam(trailerQuery):
                    queryset = queryset.filter(
                        vehicle_trailer__uf=trailerQuery)

                if is_valid_queryparam(modeQuery):
                    queryset = queryset.filter(mode__serial_number=modeQuery)

                if is_valid_queryparam(dateMinQuery):
                    queryset = queryset.filter(date_order__gte=dateMinQuery)

                if is_valid_queryparam(dateMaxQuery):
                    queryset = queryset.filter(date_order__lte=dateMaxQuery)

                if is_valid_queryparam(numMinQuery):
                    queryset = queryset.filter(rn__gte=numMinQuery)

                if is_valid_queryparam(numMaxQuery):
                    queryset = queryset.filter(rn__lte=numMaxQuery)

                if is_valid_queryparam(numMinQuery):
                    queryset = queryset.filter(rn__gte=numMinQuery)

                if is_valid_queryparam(numMaxQuery):
                    queryset = queryset.filter(rn__lte=numMaxQuery)

                if is_valid_queryparam(relDocNumQuery):
                    queryset = queryset.filter(
                        Q(rn__icontains=relDocNumQuery) | Q(trip_loads__sn__icontains=relDocNumQuery) | Q(trip_number__icontains=relDocNumQuery))

                if is_valid_queryparam(statusQuery):
                    queryset = queryset.filter(
                        status__serial_number=statusQuery)

                if is_valid_queryparam(commentQuery):
                    queryset = queryset.filter(
                        trip_comments__comment__icontains=commentQuery)

                if is_valid_queryparam(vehicleQuery):
                    queryset = queryset.filter(Q(vehicle_tractor__reg_number__icontains=vehicleQuery)
                                               | Q(vehicle_trailer__reg_number__icontains=vehicleQuery)
                                               )

                if is_valid_queryparam(startDate):
                    dts = datetime.strptime(startDate, "%Y-%m-%d")
                    dts = timezone.make_aware(dts)
                    queryset = queryset.filter(date_order__gte=dts)

                if is_valid_queryparam(endDate):
                    dte = datetime.strptime(endDate, "%Y-%m-%d")
                    dte = timezone.make_aware(dte)
                    queryset = queryset.filter(date_order__lte=dte)

            return queryset.order_by(F(order_by).desc(nulls_first=True), '-date_order')

        except Exception as e:
            logger.error(
                f'ERRORLOG2017 TripListView. filter_queryset. Error: {e}')

            return queryset


class TripCreateView(CreateAPIView):
    pagination_class = LimitResultsSetPagination
    serializer_class = TripCreateUpdateSerializer
    http_method_names = ['head', 'post']
    permission_classes = [IsAuthenticated,
                          HasGroupPermission
                          # IsSubscriptionActiveOrReadOnly
                          ]
    required_groups = {
        'HEAD': ['type_carrier'],
        'GET': ['type_carrier'],
        'POST': ['type_carrier'],
    }

    def get_queryset(self):

        user_company = get_user_company(self.request.user)
        queryset = Trip.objects.filter(company__id=user_company.id)

        print('2828')

        return queryset

    def post(self, request, *args, **kwargs):
        print('8254')
        num = 'rn'
        item = None
        queryset = self.get_queryset()
        new_item_num = self.request.data.get(num, None)
        if check_not_unique_num(item, queryset, new_item_num, num):
            return Response(status=status.HTTP_409_CONFLICT)
        print('5454')
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
            print('EV251', e)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TripDetailView(RetrieveUpdateDestroyAPIView):
    lookup_field = 'uf'
    permission_classes = [IsAuthenticated, HasGroupPermission,
                          AssignedUserManagerOrReadOnlyIfLocked
                          # IsSubscriptionActiveOrReadOnly
                          ]
    http_method_names = ['head', 'get', 'patch', 'delete']
    required_groups = {
        'HEAD': ['type_carrier'],
        'GET': ['type_carrier',],
        'PUT': ['type_carrier',],
        'DELETE': ['type_carrier'],
    }

    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return TripCreateUpdateSerializer
        return TripSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        queryset = Trip.objects.filter(company_id=user_company.id)

        queryset = queryset.select_related(
            'carrier', 'carrier__country_code_post').select_related('mode').select_related('bt').\
            select_related('currency').select_related('status').select_related(
                'vehicle_tractor').select_related('vehicle_trailer')

        trip_comments = Comment.objects.all()

        trip_loads = Load.objects.select_related(
            'bill_to', 'bill_to__country_code_post').select_related(
            'status').select_related('mode').select_related('bt').select_related('currency').\
            select_related('incoterm').select_related(
            'assigned_user').filter(company__id=user_company.id)

        load_comments = Comment.objects.all()

        load_entries = Entry.objects.select_related(
            'shipper', 'shipper__company', 'shipper__country_code_site', 'shipper__country_code_site').prefetch_related('entry_details').all()

        itemInvs = ItemInv.objects.select_related(
            'item_for_item_inv').select_related('item_for_item_cost').all()

        load_tors = Tor.objects.filter(company__id=user_company.id).select_related(
            'carrier')

        load_tors = load_tors.prefetch_related(
            Prefetch('tor_iteminvs', queryset=itemInvs))

        load_exps = Exp.objects.filter(company__id=user_company.id).select_related(
            'supplier', 'supplier__country_code_post')

        trip_loads = trip_loads.prefetch_related(
            Prefetch('load_comments', queryset=load_comments)).prefetch_related(
            Prefetch('entry_loads', queryset=load_entries)).prefetch_related(
            Prefetch('load_iteminvs', queryset=itemInvs)).prefetch_related(
            Prefetch('load_tors', queryset=load_tors)).prefetch_related(Prefetch('load_exps', queryset=load_exps))

        route_sheet_qs = RouteSheet.objects.filter(company_id=user_company.id).select_related(
            'company',
            'assigned_user',
            'trip',
            'start_location',
            'end_location',
            'vehicle_tractor',
            'vehicle_trailer',
            'currency',
        ).prefetch_related('drivers')

        drivers_qs = user_company.user.all()

        queryset = queryset.prefetch_related(
            Prefetch('trip_comments', queryset=trip_comments),
            Prefetch('trip_loads', queryset=trip_loads),
            Prefetch('trip_route_sheets', queryset=route_sheet_qs),
            Prefetch('drivers', queryset=drivers_qs),

        )

        # print('4436')
        return queryset

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        new_tn = self.request.data.get('tn')

        if new_tn:
            exists = Trip.objects.filter(
                company=instance.company,
                rn=new_tn
            ).exclude(uf=instance.uf).only('id').exists()
            if exists:
                return Response({"detail": "TN already exists"}, status=status.HTTP_409_CONFLICT)

        assigned_user_id = instance.assigned_user.id if instance.assigned_user else None
        if not is_user_member_group(request.user, 'level_manager') and assigned_user_id != self.request.user.id:
            # print('8480', request.data.pop('is_locked'))
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
                assigned_user = self.request.user

        except Exception as e:
            logger.error(f'EV207 TripDetail. perform_update. Error: {e}')

        # print('2076', assigned_user)

        start = time.time()

        serializer.save(changed_by=self.request.user,
                        assigned_user=assigned_user)

        print("SERIALIZER TIME:", time.time() - start)
