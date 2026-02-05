INITIAL_VALIDITY_OF_SUBSCRIPTION_DAYS = 30


BASE_COUNTRIES = (('ro', 'Romania'),
                  ('md', 'Moldova'),
                  ('ua', 'Ukraine'),
                  ('eu', 'Other EU country'),
                  )

BASE_COUNTRIES_LIST = ['ro', 'md', 'ua', 'eu']

APP_LANGS = ('ro', 'en', 'ru')

APP_LANGS_TUPLE = (("en", "English"),
                   ("ro", "Romanian"),
                   ("ru", "Russian"),)


MEMBERSHIP_CHOICES = (('basic', 'basic'), ('pro', 'pro'),
                      ('premium', 'premium'))


VEHICLE_TYPES = (('truck', 'Truck'), ('tractor', 'Tractor'),
                 ('trailer', 'Trailer'))


LOAD_SIZE = (('ltl', 'LTL'), ('ftl', 'FTL'), ('xpr', 'XPR'))

LOAD_TYPES = (('own', 'Own'), ('external', 'External'), ('local', 'Local'))

DOC_LANG_CHOICES = (('ro', 'Romanian'), ('en', 'English'),
                    ('ru', 'Russian'), ('rr', 'Romanian/Russian'))


DOCUMENT_TYPES = [
    ('load', 'Load'),
    ('trip', 'Trip'),
    ('tor', 'Order to carrier'),
    ('ctr', 'Customer Order'),
    ('quote', 'Quote'),
    ('inv', 'Invoice'),
    ('pf', 'Proforma Invoice'),
    ('exp', 'Expense'),
]

ALLOWED_TYPE_ACCOUNT_GROUPS_TO_ADD = (
    'type_shipper', 'type_forwarder', 'type_carrier')


ACTION_CHOICES = (('loading', 'Loading'), ('unloading', 'Unloading'),
                  ('parking', 'Parking'), ('clearance', 'Customs stop'))


UNIT_MEASUREMENT_CHOICES = (
    ('pc', 'Piece'), ('kg', 'Kg'), ('t', 'Tonne'), ('cbm', 'CBM'), ('lt', 'Litre'))


VAT_CHOICES = ((21, '21%'), (20, '20%'), (19, '19%'),
               (11, '11%'), (9, '9%'), (5, '5%'), (0, '0%'))

VAT_TYPE_CHOICES = (('normal', 'Normal'), ('reduced', 'Reduced'), ('zero', 'Zero'),
                    ('sfdd', 'SFDD'), ('sdd', 'SDD'), ('reverse_charge', 'Reverse charge'), ('exempt', 'Exempt'))


VAT_EXEMPTION_REASON = (('vatex-eu-g', 'VATEX-EU-G'),
                        ('vatex-eu-ic', 'VATEX-EU-IC'), ('vatex-eu-o', 'VATEX-EU-O'), ('vatex-eu-ae', 'VATEX-EU-AE'))


DOC_LANG_CHOICES = (('ro', 'Romanian'), ('en', 'English'),
                    ('ru', 'Russian'), ('rr', 'Romanian/Russian'))


DOCUMENT_STATUS_CHOICES = (
    ('free', 'Free'), ('reserved', 'Reserved'), ('used', 'Used'))


EMAIL_TEMPLATE_CODES = {
    "request_info_from_shipper",
    "request_info_from_consignee",
    "send_docs_to_import_broker",
    "send_documents_to_customer",
}

SYSTEM_LABELS = [
    ("inbox", "Inbox", 1),
    ("sent", "Sent", 2),
    ("drafts", "Drafts", 3),
    ("trash", "Trash", 99),
]
