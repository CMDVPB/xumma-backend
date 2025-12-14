INITIAL_VALIDITY_OF_SUBSCRIPTION_DAYS = 30


BASE_COUNTRIES = (('ro', 'Romania'),
                  ('md', 'Moldova'),
                  ('ua', 'Ukraine'),
                  ('eu', 'Other EU country'),
                  )

BASE_COUNTRIES_LIST = ['ro', 'md', 'ua', 'eu']

APP_LANGS = ('ro', 'en', 'ru')


MEMBERSHIP_CHOICES = (('basic', 'basic'), ('pro', 'pro'),
                      ('premium', 'premium'))


VEHICLE_TYPES = (('truck', 'Truck'), ('tractor', 'Tractor'),
                 ('trailer', 'Trailer'))


LOAD_SIZE = (('ltl', 'LTL'), ('ftl', 'FTL'), ('xpr', 'XPR'))

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
