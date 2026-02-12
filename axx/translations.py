VALID_DOC_TYPES = ["invoice", "proforma", "credit_note"]


TRANSLATIONS = {
    "en": {
        "titles": {
            "invoice": "Invoice",
            "proforma": "Proforma",
            "credit_note": "Credit Note",
        },
        "seller": "Seller",
        "buyer": "Buyer",
        "invoice_number": "Invoice #",
        "date": "Date",
        "due_date": "Due Date",
        "customer_ref": "Customer Ref.",
        "currency": "Currency",
        "service": "Service",
        "quantity": "Quantity",
        "unit_price": "Unit Price",
        "amount": "Amount",
        "notes": "Notes",
        "iban": "IBAN",

        "act_title": 'Act of confirmation of executed services',
        "nr": "Nbr.",
        "from": "from",
        "parties": "Parties",
        "signature_name": 'Name',
        "signature_stamp": 'Signature/ stamp',
    },
    "ro": {
        "titles": {
            "invoice": "Factura",
            "proforma": "Cont de plata",
            "credit_note": "Storno / Nota de Credit",
        },
        "seller": "Vanzator",
        "buyer": "Cumparator",
        "invoice_number": "Cont de plata #",
        "date": "Data",
        "due_date": "Scadenta",
        "customer_ref": "Ref. client",
        "currency": "Valuta",
        "service": "Serviciu",
        "quantity": "Cantitatea",
        "unit_price": "Pret unitar",
        "amount": "Valoarea",
        "notes": "Nota",
        "iban": "IBAN",

        "act_title": 'Act de confirmare a serviciilor prestate',
        "nr": "Nr.",
        "from": "din",
        "parties": "Partile",
        "signature_name": 'Prenume / Nume',
        "signature_stamp": 'Semnatura / stampila',
    },
    "ru": {
        "titles": {
            "invoice": "Счёт",
            "proforma": "Счёт к оплате",
            "credit_note": "Кредит-нота",
        },
        "seller": "Продавец",
        "buyer": "Покупатель",
        "invoice_number": "Счёт к оплате №",
        "date": "Дата",
        "due_date": "Срок оплаты",
        "customer_ref": "Клиент",
        "currency": "Валюта",
        "service": "Услуга",
        "quantity": "Количество",
        "unit_price": "Цена",
        "amount": "Сумма",
        "notes": "Примечание",
        "iban": "IBAN",


        "act_title": 'Акт подтверждения выполненных услуг',
        "nr": "№",
        "from": "от",
        "parties": "Стороны",
        "signature_name": 'Имя / Фамилия',
        "signature_stamp": 'Подпись/ печать',
    }
}


SUPPORTED_LANGUAGES = {"en", "ro", "ru"}


def resolve_language(user=None, customer=None, userSentLang=None) -> str:
    """
    Language resolution rules:

    1. If customer country != 'md' → force English
    2. Else use user.language if valid
    3. Fallback → default (English)
    """

    default = 'en'

    print('CUSTOMER RESOLVE LANGUAGE',  userSentLang)

    if userSentLang:
        return userSentLang

    try:
        # ---- Country override rule
        if customer:
            country = country = getattr(
                getattr(customer, "country_code_legal", None),
                "label",
                None
            )

            print('CUSTOMER COUNTRY', country)

            if country and str(country).lower() != "md":
                return "en"
            if country and str(country).lower() == "md":
                return "ro"

        # # ---- User preference
        # if user:
        #     lang = getattr(user, "language", None)

        #     if lang:
        #         lang = str(lang).lower()

        #         if lang in SUPPORTED_LANGUAGES:
        #             return lang

    except Exception:
        # Never allow language logic to break document generation
        pass

    return default
