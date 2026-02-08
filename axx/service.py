from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.core.files.base import ContentFile

from axx.models import LoadDocument, LoadInv
from axx.utils_generate import generate_order_pdf, generate_proforma_pdf


@transaction.atomic
def issue_invoice(load, user, data):
    last_number = (
        LoadInv.objects
        .filter(company=load.company, status='issued')
        .select_for_update()
        .aggregate(Max('invoice_number'))
        .get('invoice_number__max')
    )

    next_number = None

    invoice = LoadInv.objects.create(
        load=load,
        company=load.company,
        invoice_number=next_number,
        issued_by=user,
        issued_date=load.date_cleared,

        amount_mdl=data['invoice_amount'],
        exchange_rate=data['exchange_rate'],
        rate_date=data['rate_date'],

        original_amount=load.freight_price,
        currency=load.currency.currency_code,
        amount_overridden=data['is_overridden'],

        status='issued',
    )

    return invoice

###### START PDF GENERATION LOGIC ######


def safe_str(value, default="-"):
    return str(value) if value not in (None, "") else default


def safe_date(value, default="-", fmt="%b %d %Y"):
    try:
        return value.strftime(fmt)
    except Exception:
        return default


def safe_money(value, currency=None, default="0.00"):
    if value is None:
        return default if not currency else f"{default} {currency}"
    return f"{value} {currency}" if currency else str(value)


def safe_fk(obj, fk_attr, field, default="-"):
    try:
        return getattr(getattr(obj, fk_attr), field)
    except Exception:
        return default


def build_proforma_data(load) -> dict:
    company = getattr(load, "company", None)
    bill_to = getattr(load, "bill_to", None)

    currency = safe_str(
        getattr(
            getattr(load, "currency", None),
            "currency_code",
            None,
        ),
        "",
    )

    return {
        "title": "Cont de plata",

        "from": {
            "name": safe_str(getattr(company, "name", "Compania Mea SRL")),
            "address": [
                safe_str(getattr(company, "address_line1",
                         "Strada Industriala, 1000, bir. 100")),
                safe_str(
                    f"{getattr(company, 'postcode', '2020')} {getattr(company, 'city', 'Chisinau')}".strip(
                    )
                ),
                safe_str(getattr(company, "country", 'MD')),
            ],
            "iban": safe_str(getattr(company, "iban", 'MD00TESTIBAN0000000000456')),
        },

        "to": {
            "name": safe_str(getattr(bill_to, "company_name", None)),
            "address": [
                safe_str(getattr(bill_to, "address_legal", None)),
                safe_str(
                    f"{getattr(bill_to, 'zip_code_legal', '')} {getattr(bill_to, 'city_legal', '')}".strip(
                    )
                ),
                safe_str(
                    getattr(
                        getattr(bill_to, "country_code_legal", None),
                        "country_code",
                        None,
                    )
                )
            ],
        },

        "meta": {
            "number": safe_str(getattr(load, "invoice_number", None)),
            "date": safe_date(getattr(load, "date_cleared", None)),
            "due_date": safe_date(getattr(load, "invoice_due_date", None)),
            "customer_ref": safe_str(getattr(load, "customer_ref", None)),
        },

        "rows": [
            {
                "description": safe_str(getattr(load, "service_description", 'Transport rutier internatioal de marfa')),
                "quantity": "1",
                "rate": safe_money(getattr(load, "freight_price", None), currency),
                "amount": safe_money(getattr(load, "freight_price", None), currency),
            }
        ],

        "totals": [
            {
                "label": "Sub Total",
                "amount": safe_money(getattr(load, "freight_price", None), currency),
            },
            {
                "label": f"VAT ({safe_str(getattr(load, 'vat_rate', None), '0')}%)",
                "amount": safe_money(getattr(load, "vat_amount", None), currency),
            },
            {
                "label": "Total",
                "amount": safe_money(getattr(load, "freight_price", None), currency),
                "bold": True,
            },
        ],

        "notes": safe_str(getattr(load, "invoice_notes", None)),
    }


def build_order_data(load) -> dict:
    bill_to = getattr(load, "bill_to", None)

    contract = None
    if bill_to:
        contract = (
            bill_to.contact_contracts
            .order_by("-date")
            .first()
        )

    return {
        "title": safe_str(getattr(contract, "title", None), "Comandă de transport"),

        "meta": {
            "number": safe_str(getattr(contract, "number", None)),
            "date": safe_date(getattr(contract, "date", None)),
        },

        "from": {
            "name": safe_str(getattr(load.company, "name", None)),
            "address": [
                safe_str(getattr(load.company, "address_line1", None)),
                safe_str(
                    f"{getattr(load.company, 'postcode', '')} {getattr(load.company, 'city', '')}".strip()),
                safe_str(getattr(load.company, "country", None)),
            ],
        },

        "to": {
            "name": safe_str(getattr(bill_to, "name", None)),
            "address": [
                safe_str(getattr(bill_to, "address_line1", None)),
                safe_str(
                    f"{getattr(bill_to, 'postcode', '')} {getattr(bill_to, 'city', '')}".strip()),
                safe_str(safe_fk(bill_to, "country_code_legal", "country_code")),
            ],
        },

        # 🔥 IMPORTANT: raw HTML, DO NOT TOUCH
        "content_html": getattr(contract, "content", "") or "",
    }


def build_act_data(load) -> dict:
    data = build_proforma_data(load)
    data["title"] = "Act of Execution of Services"
    return data


DOCUMENT_GENERATORS = {
    "proforma": {"builder": build_proforma_data, "generator": generate_proforma_pdf, "filename": "Proforma", },
    "order": {"builder": build_order_data, "generator": generate_order_pdf, "filename": "Customer Order", },
    "act": {"builder": build_act_data, "generator": generate_proforma_pdf, "filename": "Act of Execution of Services", },
}


class LoadDocumentService:

    @staticmethod
    @transaction.atomic
    def generate(load, doc_type: str, user):
        if doc_type not in DOCUMENT_GENERATORS:
            raise ValueError(f"Unsupported document type: {doc_type}")

        config = DOCUMENT_GENERATORS[doc_type]

        # 1. Find active document
        old_doc = LoadDocument.objects.filter(
            load=load,
            doc_type=doc_type,
            is_active=True
        ).first()

        new_version = (old_doc.version + 1) if old_doc else 1

        # 2. Build data
        invoice_data = config["builder"](load)

        # 3. Generate PDF bytes
        pdf_bytes = config["generator"](invoice_data)

        # 4. Deactivate old
        if old_doc:
            old_doc.is_active = False
            old_doc.save(update_fields=["is_active"])

        # 5. Save new
        doc = LoadDocument.objects.create(
            load=load,
            doc_type=doc_type,
            version=new_version,
            generated_by=user,
            is_active=True,
        )

        filename = f"{doc_type}_v{new_version}.pdf"
        doc.file.save(filename, ContentFile(pdf_bytes), save=True)

        return doc
###### END PDF GENERATION LOGIC ######
