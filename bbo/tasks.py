from xumma.celery import app

from bbo.utils import process_driver_documents, process_user_birthdays, process_vehicle_documents


@app.task(bind=True, retry_backoff=30, retry_kwargs={'max_retries': 5})
def generate_document_expiration_notifications(self):
    process_driver_documents()
    process_vehicle_documents()
    process_user_birthdays()
