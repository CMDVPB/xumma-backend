import re
import os
from datetime import date
from django.conf import settings

from axx.translations import VALID_DOC_TYPES


INVOICE_NUMBER_RE = re.compile(
    r'^INV-(\d{4})-(\d+)$'
)


def generate_next_invoice_number(last_invoice_number: str | None) -> str:
    """
    Generate next invoice number in format:
    INV-YYYY-XXXXXX
    """

    current_year = date.today().year

    # No previous invoice
    if not last_invoice_number:
        return f'INV-{current_year}-000001'

    match = INVOICE_NUMBER_RE.match(last_invoice_number)

    # If format is unexpected → reset safely
    if not match:
        return f'INV-{current_year}-000001'

    year, seq = match.groups()
    seq = int(seq)

    # New year → reset counter
    if int(year) != current_year:
        return f'INV-{current_year}-000001'

    return f'INV-{current_year}-{seq + 1:06d}'


def resolve_inv_type_title(load):

    DEFAULT_DOC_TYPE = "proforma"
    DEFAULT_FOREIGN_DOC_TYPE = "invoice"

    # print('PROFORMA DATA', load)

    bill_to = getattr(load, "bill_to", None)
    country = getattr(
        getattr(bill_to, "country_code_legal", None), "label", None)

    if country and country.upper() != "MD":
        return DEFAULT_FOREIGN_DOC_TYPE

    return DEFAULT_DOC_TYPE


DOC_TYPES = ["order", "proforma", "act"]


def get_load_document_paths(load):
    documents = (
        load.load_documents
        .filter(is_active=True, doc_type__in=DOC_TYPES)
    )

    by_type = {doc.doc_type: doc for doc in documents}

    return {
        key: (
            by_type[key].file.path
            if key in by_type
            and by_type[key].file
            and os.path.exists(by_type[key].file.path)
            else None
        )
        for key in DOC_TYPES
    }
