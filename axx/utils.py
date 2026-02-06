import re
from datetime import date


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
