### Depenencies to be run in separate containers (or terminals in development)

- Django 5.2x
- Celery (2 queues)
- Celery beat
- Redis
- postgres

### Celery

- start in development:
  - %h automatically adds the hostname
    celery -A xumma worker --loglevel=INFO --concurrency=1 -P solo -E -Q celery -n celery@%h ////// (for all other tasks)
    \*\*\* -P solo = one task at a time, fine for development on windows

### Celery beat

- start in development:
  celery -A xumma beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
- start in production:
  docker compose
