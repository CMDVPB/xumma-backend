### Depenencies to be run in separate containers (or terminals in development)

- Django 5.2x
- Celery (2 queues)
- Celery beat
- Redis
- postgres

### Start server

- start in development:
  - python -m daphne -v 2 xumma.asgi:application \*\*\* -v 2 allows logging even of info logs, hot reload not supported \*\*\*
  - uvicorn xumma.asgi:application --reload \*\*\* use uvicorn for hot reload \*\*\*
- start in production:
  docker compose (use file docker-compose.prod.yaml at root directory)

### Celery

- start in development:
  - %h automatically adds the hostname ////// (for all other tasks)
    celery -A xumma.celery:app worker --loglevel=INFO --concurrency=1 -P solo -E -Q celery -n celery@%h
    \*\*\* -P solo = one task at a time, fine for development on windows \*\*\*
- start in production:
  docker compose (use file docker-compose.prod.yaml at root directory)

### Celery beat

- start in development:
  celery -A xumma.celery:app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
- start in production:
  docker compose (use file docker-compose.prod.yaml at root directory)

### How to start (needs to be created in Admin)

- add Groups: level_manager, level_leader, level_dispatcher, level_finance, level_driver, level_employee
- add Groups: type_shipper, type_forwarder, type_carrier
- add Memberships: basic, pro, premium

### Import countries, currencies

expected currencies input:
currency_code
currency_name
currency_symbol
currency_numeric

# Example CSV:

currency_code,currency_name,currency_symbol,currency_numeric
EUR,Euro,€,978
USD,US Dollar,$,840
MDL,Moldovan Leu,L,498
RON,Romanian Leu,lei,946

command: python manage.py import_currencies xumma_data/currencies.csv
