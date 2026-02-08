
import pdfkit
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponse
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
import tempfile

from abb.constants import LOAD_DOCUMENT_TYPES
from abb.utils import get_user_company
from axx.models import Load, LoadDocument
from axx.service import LoadDocumentService
from axx.utils_generate import generate_proforma_pdf


from .models import DocumentTemplate
from .serializers import DocumentTemplateSerializer


class DefaultDocumentTemplateView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTemplateSerializer

    def get(self, request):
        doc_type = request.query_params.get('type')
        language = request.query_params.get('language')

        if not doc_type or not language:
            return Response(
                {'detail': 'type and language are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = get_user_company(request.user)

        template = DocumentTemplate.objects.filter(
            company=company,
            type=doc_type,
            is_default=True,
            is_active=True,
        ).first()

        if not template:
            return Response(
                {'detail': 'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(
            template,
            context={'language': language}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftInvoicePreviewView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_uf):
        load = get_object_or_404(Load, uf=load_uf)
        company = load.company

        seller = {
            "company_name": company.company_name,
            "fiscal_code": company.fiscal_code,
            "vat_code": company.vat_code,
            "country": company.country_code_legal,
            "zip": company.zip_code_legal,
            "city": company.city_legal,
            "address": company.address_legal,
        }

        buyer_company = load.bill_to

        buyer = {
            "company_name": buyer_company.company_name,
            "fiscal_code": buyer_company.fiscal_code,
            "vat_code": buyer_company.vat_code,
            "country": buyer_company.country_code_legal,
            "zip": buyer_company.zip_code_legal,
            "city": buyer_company.city_legal,
            "address": buyer_company.address_legal,
        }

        html = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8">
            <style>
              body {{
                font-family: Arial, sans-serif;
                font-size: 12px;
                color: #000;
              }}

              .section-title {{
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 6px;
                text-transform: uppercase;
              }}

              .seller {{
                width: 100%;
                margin-bottom: 20px;
              }}

              .seller-name {{
                font-weight: bold;
                margin-bottom: 6px;
              }}

              .seller-table {{
                width: 100%;
                border-collapse: collapse;
              }}

              .seller-table td {{
                padding: 2px 0;
                vertical-align: top;
              }}

              .seller-table .label {{
                width: 120px;
                font-weight: bold;
              }}

              .buyer {{
                    width: 100%;
                    margin-bottom: 20px;
                }}

            .buyer-name {{
                font-weight: bold;
                margin-bottom: 6px;
            }}

            .buyer-table {{
                width: 100%;
                border-collapse: collapse;
            }}

            .buyer-table td {{
                padding: 2px 0;
                vertical-align: top;
            }}

              
            </style>
          </head>
          <body>

            <div class="seller">
              <div class="section-title">Seller</div>

              <div class="seller-name">
                {seller['company_name']}
              </div>

              <table class="seller-table">
                <tr>
                  <td class="label">Fiscal code:</td>
                  <td>{seller['fiscal_code']}</td>
                </tr>
                <tr>
                  <td class="label">VAT:</td>
                  <td>{seller['vat_code']}</td>
                </tr>
                <tr>
                  <td class="label">Address:</td>
                  <td>
                    {seller['address']}<br>
                    {seller['zip']} {seller['city']}<br>
                    {seller['country']}
                  </td>
                </tr>
              </table>
            </div>

            <div class="buyer">
                <div class="section-title">Buyer</div>

                <div class="buyer-name">
                    {buyer['company_name']}
                </div>

                <table class="buyer-table">
                    <tr>
                    <td class="label">Fiscal code:</td>
                    <td>{buyer['fiscal_code']}</td>
                    </tr>
                    <tr>
                    <td class="label">VAT:</td>
                    <td>{buyer['vat_code']}</td>
                    </tr>
                    <tr>
                    <td class="label">Address:</td>
                    <td>
                        {buyer['address']}<br>
                        {buyer['zip']} {buyer['city']}<br>
                        {buyer['country']}
                    </td>
                    </tr>
                </table>
                </div>


          </body>
        </html>
        """

        config = pdfkit.configuration(
            wkhtmltopdf=settings.WKHTMLTOPDF_CMD
        )

        pdf_bytes = pdfkit.from_string(
            html,
            False,
            configuration=config,
            options={
                "encoding": "UTF-8",
                "page-size": "A4",
                "margin-top": "15mm",
                "margin-bottom": "15mm",
                "margin-left": "15mm",
                "margin-right": "15mm",
                "enable-local-file-access": "",
            },
        )

        response = HttpResponse(
            pdf_bytes,
            content_type="application/pdf",
        )
        response["Content-Disposition"] = (
            f'inline; filename="proforma_{load.uf}.pdf"'
        )
        response["Cache-Control"] = "no-store"

        return response


class HtmlToPdfPreviewView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        html = request.data.get("html")

        if not html:
            raise ValidationError({"html": "HTML content is required"})

        config = pdfkit.configuration(
            wkhtmltopdf=settings.WKHTMLTOPDF_CMD
        )

        pdf_bytes = pdfkit.from_string(
            html,
            False,
            configuration=config,
            options={
                "encoding": "UTF-8",
                "page-size": "A4",
                "margin-top": "15mm",
                "margin-bottom": "15mm",
                "margin-left": "15mm",
                "margin-right": "15mm",
                "enable-local-file-access": "",
                "disable-javascript": "",  # important for security
            },
        )

        response = HttpResponse(
            pdf_bytes,
            content_type="application/pdf",
        )
        response["Content-Disposition"] = 'inline; filename="preview.pdf"'
        response["Cache-Control"] = "no-store"

        return response


class InvoicePdfView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount", "0.00")
        notes = request.data.get("notes", "")

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)

        generate_proforma_pdf(
            filepath=tmp.name,
            amount=amount,
            notes=notes,
        )

        return FileResponse(
            open(tmp.name, "rb"),
            as_attachment=True,
            filename="invoice.pdf",
            content_type="application/pdf",
        )
