import tempfile
from django.shortcuts import get_object_or_404
from .serializers import ImportBatchDetailSerializer
from rest_framework.generics import RetrieveAPIView
from .serializers import ImportBatchListSerializer
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from .models import ImportBatch, SupplierFormat
from .serializers import ImportCreateSerializer
from .tasks import match_unmatched_import_rows_all_companies, process_import_batch


class ImportSuppliersView(APIView):
    def get(self, request):
        user_company = get_user_company(request.user)

        suppliers = (
            SupplierFormat.objects
            .filter(company=user_company, is_active=True)
            .select_related("supplier")
        )

        return Response([
            {
                "uf": sf.supplier.uf,
                "company_name": sf.supplier.company_name,
            }
            for sf in suppliers
        ])


class CostImportCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        print(request.content_type)
        print(request.data)

        serializer = ImportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = get_user_company(request.user)
        supplier_uf = serializer.validated_data["supplier_uf"]

        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"detail": "No files uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        supplier_format = get_object_or_404(
            SupplierFormat,
            company=company,
            supplier__uf=supplier_uf,
            is_active=True,
        )

        batch = ImportBatch.objects.create(
            company=company,
            supplier=supplier_format.supplier,
            period_from=serializer.validated_data["period_from"],
            period_to=serializer.validated_data["period_to"],
            created_by=request.user,
        )

        file_paths = []
        for f in files:
            tmp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f"_{f.name}"
            )

            for chunk in f.chunks():
                tmp_file.write(chunk)

            tmp_file.close()

            file_paths.append(tmp_file.name)

        process_import_batch.delay(
            batch_id=batch.id,
            supplier_format_id=supplier_format.id,
            file_paths=file_paths,
        )

        return Response(
            {
                "uf": batch.uf,
                "status": batch.status,
                "year": batch.year,
                "sequence": batch.sequence,
            },
            status=status.HTTP_201_CREATED,
        )


class CostImportListView(ListAPIView):
    serializer_class = ImportBatchListSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return (ImportBatch.objects
                .filter(
                    company=user_company
                )
                .order_by(
                    "-created_at"
                ))


class CostImportDetailView(RetrieveAPIView):
    serializer_class = ImportBatchDetailSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return ImportBatch.objects.filter(
            company=user_company
        )


class RerunCostMatchingView(APIView):
    """
    Triggers re-matching of unmatched import rows to trips.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            days_back = int(request.data.get("days_back", 30))
        except (TypeError, ValueError):
            days_back = 30

        # Safety limits
        days_back = max(1, min(days_back, 365))

        match_unmatched_import_rows_all_companies.delay(days_back)

        return Response(
            {
                "status": "started",
                "days_back": days_back,
            },
            status=status.HTTP_202_ACCEPTED,
        )
