import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, Count, DecimalField, ExpressionWrapper, Q, Value, Avg
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models.functions import TruncMonth
from django.utils.translation import gettext
from django.utils.translation import activate
from django.utils.translation import get_language_from_request
from openpyxl import Workbook
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.generics import (ListCreateAPIView, RetrieveUpdateDestroyAPIView, 
                                     UpdateAPIView, DestroyAPIView, RetrieveUpdateAPIView)
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

from abb.utils import get_user_company
from att.models import Contact
from broker.helpers import get_user_role_in_point
from broker.mixins import CompanyScopedMixin, JobVisibilityQuerysetMixin
from broker.models import BrokerBaseSalary, BrokerCommissionType, BrokerSettlement, CustomerServicePrice, CustomerServiceTierPrice, Job, JobLine, PointMembership, PointOfService, Role, ServiceType, ServiceTypeTier

from broker.permissions import IsAdminOrManager, JobAccessPermission
from broker.serializers import (BrokerEmployeePerformanceSerializer, BrokerStaffCompensationSerializer, BrokerStaffDetailsSerializer, 
                                BrokerStaffSerializer, CustomerServicePriceSerializer, JobSerializer, ServiceTypeSerializer,
                                 BrokerCustomerPricingUpsertSerializer, PointMembershipSerializer, PointOfServiceSerializer, 
                                 )
from broker.service import resolve_commission
from broker.utils import build_broker_settlement_report

logger = logging.getLogger(__name__)

User = get_user_model()

class PointListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointOfServiceSerializer

    def get_queryset(self):
        company = self.get_company()
        user = self.request.user

        base_qs = (
            PointOfService.objects
            .filter(company=company)
            .annotate(
                members_count=Count(
                    "point_memberships",
                    filter=Q(point_memberships__is_active=True),
                    distinct=True
                )
            )
        )

        # Admin / Manager → see all
        if user.groups.filter(name__in=["level_admin", "level_manager"]).exists():
            return base_qs

        # Normal users → only their active memberships
        return base_qs.filter(
            point_memberships__user=user,
            point_memberships__is_active=True,
        ).distinct()


class PointDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = PointOfServiceSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return (
            PointOfService.objects
            .filter(company=self.get_company())
            .annotate(
                members_count=Count(
                    "point_memberships",
                    filter=Q(point_memberships__is_active=True),
                    distinct=True
                )
            )
        )
    
   
    def perform_destroy(self, instance):
        if instance.point_memberships.filter(is_active=True).exists():
            raise ValidationError("Cannot delete point with active members.")

        if Job.objects.filter(point=instance).exists():
            raise ValidationError("Cannot delete point with existing jobs.")

        instance.delete()


class PointMembershipListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointMembershipSerializer

    def get_queryset(self):
        point_uf = self.kwargs["uf"]       
        return PointMembership.objects.filter(
            company=self.get_company(),
            point__uf=point_uf,
            is_active=True,
        )

    def perform_create(self, serializer):
        point = PointOfService.objects.get(
            uf=self.kwargs["uf"],
            company=self.get_company()
        )

        if serializer.validated_data["role"] == Role.LEADER:
            if PointMembership.objects.filter(
                company=self.get_company(),
                point=point,
                role=Role.LEADER,
                is_active=True
            ).exists():        
                raise ValidationError("Point already has a leader.")
            
        user = serializer.validated_data["user"]

        if get_user_company(user) != self.get_company():
            raise ValidationError("User not in this company")
        
        serializer.save(
            company=self.get_company(),
            point=point
        )


class PointMembershipDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointMembershipSerializer
    lookup_field = "uf"

    def get_queryset(self):
        return PointMembership.objects.filter(
            company=self.get_company()
        )

    def perform_destroy(self, instance):
        # soft delete
        instance.is_active = False
        instance.save()


class JobListCreateView(CompanyScopedMixin, JobVisibilityQuerysetMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, JobAccessPermission]
    serializer_class = JobSerializer

    def get_queryset(self):
        qs = (Job.objects
                .select_related("point", "customer", "assigned_to")
                .prefetch_related("job_lines")
                .filter(company=self.get_company()))

        qs = self.filter_queryset_by_visibility(qs)

        # Filters
        customer = self.request.query_params.get("customer")
        point = self.request.query_params.get("point")
        assigned_to = self.request.query_params.get("assigned_to")

        if customer:
            qs = qs.filter(customer__uf=customer)

        if point:
            qs = qs.filter(point__uf=point)

        if assigned_to:
            qs = qs.filter(assigned_to__uf=assigned_to)


        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        company = self.get_company()
        user = self.request.user

        point = serializer.validated_data["point"]

        # Admin / Manager override
        if user.groups.filter(name__in=["level_admin", "level_manager"]).exists():
            serializer.save(company=company, assigned_to=user)
            return

        # Normal team member flow
        role = get_user_role_in_point(user, company, point)

        if not role:
            raise PermissionDenied("You are not a member of this team")

        serializer.save(company=company, assigned_to=user)


class JobRetrieveUpdateDestroyView(
    CompanyScopedMixin,
    JobVisibilityQuerysetMixin,
    RetrieveUpdateDestroyAPIView
):
    permission_classes = [IsAuthenticated, JobAccessPermission]
    serializer_class = JobSerializer
    lookup_field = 'uf'

    def get_queryset(self):
        qs = (Job.objects
                .filter(company=self.get_company())
                .select_related("point", "customer")
                .prefetch_related("job_lines__service_type"))
        
        return self.filter_queryset_by_visibility(qs)
    
    
class ServiceTypeListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ServiceTypeSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = (ServiceType.objects
              .filter(company=user_company)
              .prefetch_related("pricing_tiers")
              )
        
        return qs 

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


class ServiceTypeDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = ServiceTypeSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = ServiceType.objects.filter(company=user_company)
        return qs


class CustomerServicePriceListCreateView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = CustomerServicePriceSerializer

    def get_queryset(self):
        return CustomerServicePrice.objects.filter(company=self.get_company())

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


###### START BROKER REPORTS ######
class BrokerReportsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    PERIODS = [30, 90, 180]

    def get(self, request):
        company = get_user_company(request.user)
        today = timezone.now().date()

        line_total = ExpressionWrapper(
            F("quantity") * F("unit_price_net"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )

        revenue_annotation = Coalesce(
            Sum(line_total),
            Value(0),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )

        result = {
            "top_customers": {},
            "revenue_by_point": {},
            "jobs_by_point": {},
        }

        for days in self.PERIODS:
            start_date = today - timedelta(days=days)

            # -------------------------------
            # TOP CUSTOMERS
            # -------------------------------
            top_customers_qs = (
                JobLine.objects
                .filter(
                    job__company=company,
                    job__created_at__date__gte=start_date,
                )
                .values(
                    "job__customer",
                    "job__customer__company_name",
                )
                .annotate(total_revenue=revenue_annotation)
                .order_by("-total_revenue")[:10]
            )

            result["top_customers"][days] = [
                {
                    "customer_id": item["job__customer"],
                    "name": item["job__customer__company_name"],
                    "revenue": item["total_revenue"],
                }
                for item in top_customers_qs
            ]

            # -------------------------------
            # REVENUE BY POINT
            # -------------------------------
            revenue_by_point_qs = (
                JobLine.objects
                .filter(
                    job__company=company,
                    job__created_at__date__gte=start_date,
                )
                .values(
                    "job__point",
                    "job__point__name",
                )
                .annotate(total_revenue=revenue_annotation)
                .order_by("-total_revenue")
            )

            result["revenue_by_point"][days] = [
                {
                    "point_id": item["job__point"],
                    "point_name": item["job__point__name"],
                    "revenue": item["total_revenue"],
                }
                for item in revenue_by_point_qs
            ]

            # -------------------------------
            # JOBS BY POINT
            # -------------------------------
            jobs_by_point_qs = (
                Job.objects
                .filter(
                    company=company,
                    created_at__date__gte=start_date,
                )
                .values(
                    "point",
                    "point__name",
                )
                .annotate(total_jobs=Count("id"))
                .order_by("-total_jobs")
            )

            result["jobs_by_point"][days] = [
                {
                    "point_id": item["point"],
                    "point_name": item["point__name"],
                    "total_jobs": item["total_jobs"],
                }
                for item in jobs_by_point_qs
            ]

        return Response(result)


class BrokerEmployeePerformanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_employee_stats(self, company, days):
        start_date = timezone.now() - timedelta(days=days)

        line_total = ExpressionWrapper(
            F("quantity") * F("unit_price_net"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )

        revenue_annotation = Coalesce(
            Sum(line_total),
            Value(0),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )

        qs = (
            JobLine.objects
            .filter(
                job__company=company,
                job__created_at__gte=start_date,
                job__assigned_to__isnull=False,
            )
            .values(
                "job__assigned_to",
                "job__assigned_to__first_name",
                "job__assigned_to__last_name",
            )
            .annotate(
                revenue=revenue_annotation,
                jobs=Count("job", distinct=True),
            )
            .order_by("-revenue")
        )

        return [
            {
                "employee_id": row["job__assigned_to"],
                "name": f"{row['job__assigned_to__first_name']} {row['job__assigned_to__last_name']}",
                "jobs": row["jobs"],
                "revenue": row["revenue"],
            }
            for row in qs
        ]

    def get(self, request):

        company = get_user_company(request.user) 

        data = {
            "days_30": self.get_employee_stats(company, 30),
            "days_90": self.get_employee_stats(company, 90),
            "days_180": self.get_employee_stats(company, 180),
        }

        serializer = BrokerEmployeePerformanceSerializer(data)
        return Response(serializer.data)
    

class BrokerServicePriceTrendsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_user_company(request.user)

        end = date.today().replace(day=1)
        start = (end - relativedelta(months=5))  # last 6 months including current month start

        qs = (
            JobLine.objects
            .filter(
                job__company=company,
                job__created_at__date__gte=start,
            )
            .annotate(month=TruncMonth("job__created_at"))
            .values("month", "service_type_id", "service_type__name")
            .annotate(avg_price=Avg("unit_price_net"))
            .order_by("month")
        )

        # build ordered months list
        months = []
        m = start
        for _ in range(6):
            months.append(m.strftime("%Y-%m"))
            m = (m + relativedelta(months=1))

        # index month -> position
        month_index = {m: i for i, m in enumerate(months)}

        # series map
        series_map = {}  # (service_type_id) -> {name, data[6]}
        for row in qs:
            month_key = row["month"].date().replace(day=1).strftime("%Y-%m")
            idx = month_index.get(month_key)
            if idx is None:
                continue

            st_id = row["service_type_id"]
            if st_id not in series_map:
                series_map[st_id] = {
                    "service_type_id": st_id,
                    "service_name": row["service_type__name"],
                    "data": [None] * 6,
                }

            series_map[st_id]["data"][idx] = float(row["avg_price"] or 0)

        return Response({
            "months": months,
            "series": list(series_map.values()),
        })

###### END BROKER REPORTS ######

###### START BROKER PRICING ######

class BrokerSpecialPricingCustomersListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user) 

        pricings = (
            CustomerServicePrice.objects
            .filter(company=user_company, is_active=True)
            .select_related("customer")
            .values(
                "customer__uf",
                "customer__company_name",
                "customer__alias_company_name",
            )
            .annotate(active_prices=Count("id"))
            .order_by("customer__company_name")
        )

        data = [
            {
                "customer_uf": item["customer__uf"],
                "company_name": (
                    item["customer__company_name"]
                    or item["customer__alias_company_name"]
                ),
                "active_prices": item["active_prices"],
            }
            for item in pricings
        ]

        return Response(data)


class BrokerPartnerPricingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, partner_uf):

        company = get_user_company(request.user)

        partner = get_object_or_404(
            Contact,
            uf=partner_uf,
            company=company,
        )

        services = ServiceType.objects.filter(company=company).prefetch_related(
            "pricing_tiers"
        )

        pricing = []

        for service in services:

            tiers = []

            for tier in service.pricing_tiers.all():

                special = CustomerServiceTierPrice.objects.filter(
                    company=company,
                    customer=partner,
                    service_tier=tier,
                ).first()

                tiers.append(
                        {
                            "tier_id": tier.id,
                            "from_quantity": tier.from_quantity,
                            "to_quantity": tier.to_quantity,
                            "default_price": tier.price,
                            "special_price": special.price if special else None,
                            "is_active": special.is_active if special else False,
                        }
                    )

            pricing.append(
                {
                    "service_type_id": service.id,
                    "service_name": service.name,
                    "pricing_tiers": tiers,
                }
            )

        return Response(pricing)

    def post(self, request, partner_uf):

        company = get_user_company(request.user)

        partner = get_object_or_404(
            Contact,
            uf=partner_uf,
            company=company,
        )

        serializer = BrokerCustomerPricingUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tier_id = serializer.validated_data["tier_id"]
        price = serializer.validated_data["price"]
        is_active = serializer.validated_data["is_active"]

        tier = get_object_or_404(ServiceTypeTier, id=tier_id)

        CustomerServiceTierPrice.objects.update_or_create(
            company=company,
            customer=partner,
            service_tier=tier,
            defaults={
                "price": price,
                "is_active": is_active,
            },
        )

        return Response({"success": True})

class BrokerSpecialPricingDeleteAPIView(DestroyAPIView):
    permission_classes = [IsAuthenticated]
    

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = CustomerServicePrice.objects.filter(
                company=user_company
            )

        return qs

    def delete(self, request):
        customer_id = request.data.get("customer_id")
        service_type_id = request.data.get("service_type_id")

        pricing = CustomerServicePrice.objects.filter(
            company=request.user.company,
            customer_id=customer_id,
            service_type_id=service_type_id
        ).first()

        if not pricing:
            return Response(
                {"detail": "Pricing not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        pricing.is_active = False
        pricing.save(update_fields=["is_active"])

        return Response(status=status.HTTP_204_NO_CONTENT)

###### END BROKER PRICING ######

###### START STAFF ######
class BrokerStaffListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_company = get_user_company(request.user)        

        users = User.objects.filter(
            company=user_company,
            groups__name__in=["level_leader_broker", "level_broker"],
        ).distinct()

        serializer = BrokerStaffSerializer(users, many=True)

        return Response(serializer.data)
    

class BrokerStaffDetailsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BrokerStaffDetailsSerializer
    lookup_field = "uf"

    def get_queryset(self):

        qs = User.objects.filter(
            groups__name__in=[
                "level_leader_broker",
                "level_broker",
            ]
        )
        return qs.distinct()
    

class BrokerStaffCompensationUpdateView(UpdateAPIView):

    serializer_class = BrokerStaffCompensationSerializer
    lookup_field = "uf"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = get_user_company(self.request.user)
        context["user"] = self.get_object()
        return context

    def get_queryset(self):

        qs = User.objects.filter(
            groups__name__in=[
                "level_leader_broker",
                "level_broker",
            ]
        )
        return qs.distinct()
    

class BrokerCommissionTypeListView(APIView):

    def get(self, request):

        data = [
            {
                "code": code,
                "label": gettext(label),
            }
            for code, label in BrokerCommissionType.choices
        ]

        return Response(data)
    

class BrokerSettlementReportAPIView(APIView):

    def get(self, request):

        company = get_user_company(request.user)

        broker_uf = request.query_params.get("broker")
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        broker = get_object_or_404(User, uf=broker_uf, company=company)

        report = build_broker_settlement_report(company, broker, start, end)

        return Response(report)    


class BrokerSettlementExportAPIView(APIView):

    def get(self, request):
        lang = get_language_from_request(request)
        activate(lang)

        print('LANG5060', lang)

        company = get_user_company(request.user)

        broker_uf = request.query_params.get("broker")
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        broker = get_object_or_404(User, uf=broker_uf, company=company)

        report = build_broker_settlement_report(company, broker, start, end)

        wb = Workbook()
        ws = wb.active
        ws.title = "Broker Settlement"

        # header
        ws.append([           
            gettext("Date"),
            gettext("Customer"),
            gettext("Service"),
            gettext("Quantity"),
            gettext("Revenue"),
            gettext("Commission")
        ])

        for row in report["rows"]:
            ws.append([               
                row["date"],
                row["customer"],
                row["service"],
                row["quantity"],
                float(row["revenue"]),
                float(row["commission"]),
            ])

        ws.append([])
        ws.append([gettext("Base salary"), float(report["summary"]["base_salary"])])
        ws.append([gettext("Commission total"), float(report["summary"]["commission_total"])])
        ws.append([gettext("Total income"), float(report["summary"]["total_income"])])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response["Content-Disposition"] = f'attachment; filename="broker-settlement-{broker.uf}.xlsx"'

        wb.save(response)

        return response


class BrokerSettlementCreateAPIView(APIView):

    def post(self, request):

        company = get_user_company(request.user)

        broker_uf = request.data.get("broker")
        start = request.data.get("start")
        end = request.data.get("end")

        broker = get_object_or_404(User, uf=broker_uf, company=company)

        report = build_broker_settlement_report(company, broker, start, end)

        settlement = BrokerSettlement.objects.create(
            company=company,
            broker=broker,
            period_start=start,
            period_end=end,
            base_salary=report["summary"]["base_salary"],
            commission_total=report["summary"]["commission_total"],
            total_income=report["summary"]["total_income"],
        )

        return Response({
            "uf": settlement.uf
        })

###### END STAFF ######